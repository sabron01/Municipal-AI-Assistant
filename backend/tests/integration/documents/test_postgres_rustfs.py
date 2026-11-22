"""End-to-end persistence and object-storage contract test.

Requires a dedicated migrated PostgreSQL database and a RustFS test endpoint.
The fixture creates a random bucket and removes only rows written by its actor.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
from io import BytesIO

import boto3
import pytest
from datetime import datetime, timezone
from botocore.config import Config
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker

from municipal_assistant.documents.application.use_cases import CreateDocument, DocumentService
from municipal_assistant.documents.domain.entities import DocumentVersion, VersionState
from municipal_assistant.documents.domain.errors import ConcurrentModification, DocumentNotFound
from municipal_assistant.documents.domain.value_objects import (
    CategoryId,
    ObjectKey,
    ServiceId,
    Sha256,
    VersionId,
)
from municipal_assistant.documents.infrastructure.postgres_repositories import PostgresUnitOfWork
from municipal_assistant.documents.infrastructure.rustfs_storage import RustFSObjectStorage
from municipal_assistant.documents.infrastructure.sqlalchemy_models import (
    DocumentAuditRow,
    DocumentRow,
    DocumentVersionRow,
    OutboxRow,
)
from municipal_assistant.documents.infrastructure.upload_validation import UploadValidator


REQUIRED_ENV = (
    "TEST_DATABASE_URL",
    "TEST_RUSTFS_ENDPOINT",
    "TEST_RUSTFS_ACCESS_KEY",
    "TEST_RUSTFS_SECRET_KEY",
)
pytestmark = pytest.mark.skipif(
    not all(os.getenv(name) for name in REQUIRED_ENV),
    reason="Dedicated TEST_DATABASE_URL and TEST_RUSTFS_* settings are required",
)


class ExistingReferences:
    def exists(self, _entity_id):
        return True


class AllowAllAccess:
    def require(self, _actor_id, _action, _service_id):
        return None


@pytest.fixture
def real_adapters():
    database_url = os.environ["TEST_DATABASE_URL"]
    endpoint = os.environ["TEST_RUSTFS_ENDPOINT"]
    access_key = os.environ["TEST_RUSTFS_ACCESS_KEY"]
    secret_key = os.environ["TEST_RUSTFS_SECRET_KEY"]
    bucket = f"maa-it-{uuid4().hex[:20]}"
    actor_id = uuid4()
    verify_tls = endpoint.lower().startswith("https://")

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="us-east-1",
        verify=verify_tls,
        config=Config(s3={"addressing_style": "path"}),
    )
    engine = create_engine(database_url, pool_pre_ping=True)
    sessions = sessionmaker(engine, expire_on_commit=False)
    storage = RustFSObjectStorage(endpoint=endpoint, access_key=access_key,
        secret_key=secret_key, bucket=bucket, verify_tls=verify_tls)
    service = DocumentService(
        lambda: PostgresUnitOfWork(sessions),
        storage,
        UploadValidator(max_bytes=1024 * 1024,
            allowed_media_types=frozenset({"application/pdf"})),
        ExistingReferences(),
        ExistingReferences(),
        AllowAllAccess(),
    )
    bucket_created = False
    try:
        s3.create_bucket(Bucket=bucket)
        bucket_created = True
        yield service, storage, engine, actor_id, bucket, s3
    finally:
        try:
            with engine.begin() as connection:
                document_ids = select(DocumentRow.id).where(DocumentRow.created_by == actor_id)
                version_ids = select(DocumentVersionRow.id).where(
                    (DocumentVersionRow.created_by == actor_id)
                    | DocumentVersionRow.document_id.in_(document_ids)
                )
                connection.execute(delete(DocumentAuditRow).where(
                    (DocumentAuditRow.actor_id == actor_id)
                    | DocumentAuditRow.document_id.in_(document_ids)
                ))
                connection.execute(delete(OutboxRow).where(OutboxRow.version_id.in_(version_ids)))
                connection.execute(delete(DocumentVersionRow).where(DocumentVersionRow.id.in_(version_ids)))
                connection.execute(delete(DocumentRow).where(DocumentRow.id.in_(document_ids)))
        finally:
            try:
                if bucket_created:
                    objects = s3.list_objects_v2(Bucket=bucket).get("Contents", [])
                    if objects:
                        s3.delete_objects(Bucket=bucket,
                            Delete={"Objects": [{"Key": item["Key"]} for item in objects]})
                    s3.delete_bucket(Bucket=bucket)
            finally:
                engine.dispose()


def test_document_versions_round_trip_through_postgres_and_rustfs(real_adapters):
    service, storage, _engine, actor_id, bucket, _s3 = real_adapters
    service_id, category_id = ServiceId(uuid4()), CategoryId(uuid4())
    first_body = b"%PDF-1.7\nfirst version"
    second_body = b"%PDF-1.7\nsecond version"

    document = service.create(CreateDocument("Integration report", service_id, category_id,
        "report.pdf", BytesIO(first_body)), actor_id)
    first_version = document.current_version_id
    updated = service.add_version(document.id, BytesIO(second_body), "report-v2.pdf",
        actor_id, expected_version=document.aggregate_version)

    assert len(updated.versions) == 2
    assert updated.aggregate_version == 2
    assert updated.current_version_id != first_version
    assert len(service.versions(document.id, actor_id)) == 2

    first_download = service.download(document.id, actor_id, first_version)
    try:
        assert first_download.body.read() == first_body
    finally:
        first_download.close()
    current_download = service.download(document.id, actor_id)
    try:
        assert current_download.body.read() == second_body
    finally:
        current_download.close()

    keys = [version.object_key for version in updated.versions]
    assert all(storage.head(key) is not None for key in keys)
    service.soft_delete(document.id, actor_id, expected_version=updated.aggregate_version)
    with pytest.raises(DocumentNotFound):
        service.get(document.id, actor_id)
    # Logical deletion does not remove either immutable RustFS object.
    assert all(storage.head(key) is not None for key in keys)


def test_pending_version_reservation_blocks_a_second_upload(real_adapters):
    service, _storage, _engine, actor_id, bucket, s3 = real_adapters
    document = service.create(CreateDocument("Concurrent report", ServiceId(uuid4()),
        CategoryId(uuid4()), "report.pdf", BytesIO(b"%PDF-1.7\ninitial")), actor_id)
    pending_id = VersionId(uuid4())
    pending = DocumentVersion(pending_id, document.id, 2,
        ObjectKey(f"documents/{document.id.value}/{pending_id.value}"),
        Sha256("a" * 64), 20, "application/pdf", "pending.pdf",
        datetime.now(timezone.utc), actor_id, state=VersionState.PENDING)
    with service.uow_factory() as uow:
        uow.documents.reserve_version(pending, expected_aggregate_version=document.aggregate_version)
        uow.commit()

    with pytest.raises(ConcurrentModification):
        service.add_version(document.id, BytesIO(b"%PDF-1.7\ncompeting"),
            "competing.pdf", actor_id, expected_version=document.aggregate_version)

    objects = s3.list_objects_v2(Bucket=bucket).get("Contents", [])
    assert len(objects) == 1


def test_two_simultaneous_version_uploads_have_one_winner(real_adapters):
    service, _storage, _engine, actor_id, bucket, s3 = real_adapters
    document = service.create(CreateDocument("Concurrent report", ServiceId(uuid4()),
        CategoryId(uuid4()), "report.pdf", BytesIO(b"%PDF-1.7\ninitial")), actor_id)
    barrier = Barrier(2)

    def upload(filename, payload):
        barrier.wait(timeout=10)
        return service.add_version(document.id, BytesIO(payload), filename, actor_id,
            expected_version=document.aggregate_version)

    winners, conflicts = [], []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(upload, "concurrent-a.pdf", b"%PDF-1.7\nversion a"),
                   pool.submit(upload, "concurrent-b.pdf", b"%PDF-1.7\nversion b")]
        for future in futures:
            try:
                winners.append(future.result(timeout=30))
            except ConcurrentModification as exc:
                conflicts.append(exc)

    assert len(winners) == 1
    assert len(conflicts) == 1
    assert len(service.versions(document.id, actor_id)) == 2
    assert len(s3.list_objects_v2(Bucket=bucket).get("Contents", [])) == 2

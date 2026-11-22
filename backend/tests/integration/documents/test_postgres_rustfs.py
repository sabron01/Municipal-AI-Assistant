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


def test_fastapi_document_flow_uses_account_permissions_and_csrf(real_adapters, monkeypatch):
    _service_unused, _storage, engine, actor_id, bucket, s3 = real_adapters
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    from municipal_assistant.accounts.models import (
        AccountAuditRow,
        AccountRow,
        AccountSessionRow,
        PermissionGrantRow,
    )
    from municipal_assistant.accounts.security import hash_password
    from municipal_assistant.administration.infrastructure.models import (
        CatalogAuditRow,
        CategoryRow,
        DirectionRow,
        ServiceRow,
    )
    from municipal_assistant.app import configure_documents, create_app
    from municipal_assistant.documents.infrastructure.composition import build_document_service

    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    email = f"docs-it-{uuid4().hex}@example.com"
    password = "LocalTestPassword-Long!27"
    password_hash = hash_password(password)
    app = None
    direction_id = service_id = category_id = None
    other_service_id = None
    try:
        with sessionmaker(engine, expire_on_commit=False)() as session:
            session.add(AccountRow(id=actor_id, email=email, normalized_email=email,
                password_hash=password_hash, status="active", is_central_admin=False))
            session.commit()

        app = create_app()
        direction = app.state.catalog_service.create_direction(
            name=f"Test direction {uuid4()}", actor_id=actor_id)
        service = app.state.catalog_service.create_service(
            direction_id=direction.id, name=f"Test service {uuid4()}", actor_id=actor_id)
        other_service = app.state.catalog_service.create_service(
            direction_id=direction.id, name=f"Unassigned service {uuid4()}", actor_id=actor_id)
        category = app.state.catalog_service.create_category(
            parent_id=None, name=f"Test category {uuid4()}", actor_id=actor_id)
        direction_id, service_id, category_id = direction.id, service.id, category.id
        other_service_id = other_service.id

        with sessionmaker(engine, expire_on_commit=False)() as session:
            for permission in ("document.create", "document.read", "document.version_add",
                              "document.metadata_update", "document.soft_delete"):
                session.add(PermissionGrantRow(account_id=actor_id, service_id=service_id,
                    permission=permission, granted_by=actor_id))
            session.commit()

        document_service = build_document_service(
            database_url=os.environ["TEST_DATABASE_URL"],
            object_storage_endpoint=os.environ["TEST_RUSTFS_ENDPOINT"],
            object_storage_access_key=os.environ["TEST_RUSTFS_ACCESS_KEY"],
            object_storage_secret_key=os.environ["TEST_RUSTFS_SECRET_KEY"],
            object_storage_bucket=bucket,
            max_upload_bytes=1024 * 1024,
            allowed_media_types=frozenset({"application/pdf"}),
        )
        configure_documents(app, service=document_service, actor_resolver=app.state.actor_resolver,
            business_policy_approved=True)

        with TestClient(app) as client:
            login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
            assert login.status_code == 200
            csrf = login.json()["csrf_token"]
            invalid = client.post("/api/v1/documents", headers={"X-CSRF-Token": csrf},
                data={"title": "HTTP integration report", "service_id": str(service_id),
                      "category_id": str(category_id), "unexpected": "reject me"},
                files={"file": ("report.pdf", b"%PDF-1.7\nfirst HTTP version", "application/pdf")})
            assert invalid.status_code == 422
            created = client.post("/api/v1/documents", headers={"X-CSRF-Token": csrf},
                data={"title": "HTTP integration report", "service_id": str(service_id),
                      "category_id": str(category_id)},
                files={"file": ("report.pdf", b"%PDF-1.7\nfirst HTTP version", "application/pdf")})
            assert created.status_code == 201, created.text
            document_id = created.json()["id"]
            first_version_id = created.json()["current_version_id"]

            denied_create = client.post("/api/v1/documents", headers={"X-CSRF-Token": csrf},
                data={"title": "Unassigned report", "service_id": str(other_service_id),
                      "category_id": str(category_id)},
                files={"file": ("blocked.pdf", b"%PDF-1.7\nblocked", "application/pdf")})
            assert denied_create.status_code == 404
            assert client.get("/api/v1/documents", params={"service_id": str(other_service_id)}).json()["items"] == []

            metadata = client.patch(f"/api/v1/documents/{document_id}",
                headers={"X-CSRF-Token": csrf, "If-Match": created.headers["etag"]},
                json={"title": "Renamed integration report", "service_id": str(service_id),
                      "category_id": str(category_id), "description": None, "reference_number": None})
            assert metadata.status_code == 200, metadata.text
            assert metadata.json()["title"] == "Renamed integration report"

            listed = client.get("/api/v1/documents", params={"service_id": str(service_id)})
            assert listed.status_code == 200
            assert [item["id"] for item in listed.json()["items"]] == [document_id]

            version = client.post(f"/api/v1/documents/{document_id}/versions",
                headers={"X-CSRF-Token": csrf, "If-Match": metadata.headers["etag"]},
                files={"file": ("report-v2.pdf", b"%PDF-1.7\nsecond HTTP version", "application/pdf")})
            assert version.status_code == 201, version.text
            stale_version = client.post(f"/api/v1/documents/{document_id}/versions",
                headers={"X-CSRF-Token": csrf, "If-Match": created.headers["etag"]},
                files={"file": ("stale.pdf", b"%PDF-1.7\nstale", "application/pdf")})
            assert stale_version.status_code == 412

            old_content = client.get(f"/api/v1/documents/{document_id}/content",
                params={"version_id": first_version_id})
            current_content = client.get(f"/api/v1/documents/{document_id}/content")
            assert old_content.content == b"%PDF-1.7\nfirst HTTP version"
            assert current_content.content == b"%PDF-1.7\nsecond HTTP version"

            deleted = client.delete(f"/api/v1/documents/{document_id}",
                headers={"X-CSRF-Token": csrf, "If-Match": version.headers["etag"]})
            assert deleted.status_code == 204
            assert client.get(f"/api/v1/documents/{document_id}").status_code == 404
            assert len(s3.list_objects_v2(Bucket=bucket).get("Contents", [])) == 2
    finally:
        try:
            with engine.begin() as connection:
                connection.execute(delete(PermissionGrantRow).where(
                    (PermissionGrantRow.account_id == actor_id)
                    | (PermissionGrantRow.granted_by == actor_id)))
                connection.execute(delete(AccountSessionRow).where(AccountSessionRow.account_id == actor_id))
                connection.execute(delete(AccountAuditRow).where(
                    (AccountAuditRow.actor_id == actor_id) | (AccountAuditRow.subject_id == actor_id)))
                connection.execute(delete(CatalogAuditRow).where(CatalogAuditRow.actor_id == actor_id))
                if category_id is not None:
                    connection.execute(delete(CategoryRow).where(CategoryRow.id == category_id))
                if service_id is not None:
                    connection.execute(delete(ServiceRow).where(
                        ServiceRow.id.in_([value for value in (service_id, other_service_id) if value is not None])))
                if direction_id is not None:
                    connection.execute(delete(DirectionRow).where(DirectionRow.id == direction_id))
                connection.execute(delete(AccountRow).where(AccountRow.id == actor_id))
        finally:
            if app is not None and app.state.account_engine is not None:
                app.state.account_engine.dispose()

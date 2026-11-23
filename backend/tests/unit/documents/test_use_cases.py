from dataclasses import replace
from datetime import date
from io import BytesIO
from uuid import uuid4

import pytest

from municipal_assistant.documents.application.use_cases import CreateDocument, DocumentService
from municipal_assistant.documents.domain.entities import VersionState
from municipal_assistant.documents.domain.errors import DocumentNotFound
from municipal_assistant.documents.domain.ports import StoredObjectMetadata, StoredObjectReceipt
from municipal_assistant.documents.domain.value_objects import CategoryId, ServiceId
from municipal_assistant.documents.infrastructure.upload_validation import UploadValidator


class MemoryRepository:
    def __init__(self):
        self.documents = {}
        self.versions_by_id = {}
        self.outbox = set()

    def get(self, document_id, *, include_deleted=False):
        item = self.documents.get(document_id.value)
        if item is None or (item.status.value == "deleted" and not include_deleted):
            return None
        if item.status.value == "pending" and not include_deleted:
            return None
        return item

    def save(self, document, *, expected_aggregate_version=None):
        self.documents[document.id.value] = document

    def reserve_version(self, version, *, expected_aggregate_version=None):
        self.versions_by_id[version.id.value] = version
        self.outbox.add(version.id.value)

    def next_sequence(self, document_id):
        sequences = [item.sequence for item in self.versions_by_id.values()
                     if item.document_id == document_id]
        return max(sequences, default=0) + 1

    def mark_version_available(self, version_id):
        self.versions_by_id[version_id.value] = replace(
            self.versions_by_id[version_id.value], state=VersionState.AVAILABLE)

    def complete_outbox(self, version_id):
        self.outbox.discard(version_id.value)

    def versions(self, document_id):
        return sorted((version for version in self.versions_by_id.values()
                       if version.document_id == document_id), key=lambda item: item.sequence)

    def pending_uploads(self):
        return []

    def list(self, _query):
        raise NotImplementedError


class MemoryUnitOfWork:
    def __init__(self, repository, audit_events):
        self.documents = repository
        self.audit = self
        self.audit_events = audit_events

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def commit(self):
        pass

    def record(self, *, actor_id, action, document_id, version_id=None, outcome="success"):
        self.audit_events.append((actor_id, action, document_id, version_id, outcome))


class MemoryStorage:
    def __init__(self, *, corrupt_checksum=False):
        self.objects = {}
        self.corrupt_checksum = corrupt_checksum
        self.put_calls = 0

    def put(self, *, key, body, content_length, content_type, checksum_sha256):
        payload = body.read()
        self.put_calls += 1
        self.objects[key.value] = (payload, content_type, checksum_sha256)
        returned_checksum = checksum_sha256
        if self.corrupt_checksum:
            from municipal_assistant.documents.domain.value_objects import Sha256
            returned_checksum = Sha256("0" * 64)
        return StoredObjectReceipt(key, content_length, returned_checksum)

    def head(self, key):
        stored = self.objects.get(key.value)
        if stored is None:
            return None
        payload, content_type, checksum = stored
        return StoredObjectMetadata(key, len(payload), checksum, content_type)

    def open(self, *_args, **_kwargs):
        raise NotImplementedError

    def delete(self, *_args, **_kwargs):
        raise NotImplementedError


class AllowAllAccess:
    def __init__(self, *, denied=False):
        self.denied = denied
        self.calls = []

    def require(self, actor_id, action, service_id):
        self.calls.append((actor_id, action, service_id))
        if self.denied:
            raise DocumentNotFound("Document was not found")


class ExistingReferences:
    def exists(self, _id):
        return True


def make_service(*, storage=None, access=None):
    repository, audit_events = MemoryRepository(), []
    storage = storage or MemoryStorage()
    access = access or AllowAllAccess()
    service = DocumentService(
        lambda: MemoryUnitOfWork(repository, audit_events),
        storage,
        UploadValidator(max_bytes=1024, allowed_media_types=frozenset({"application/pdf"})),
        ExistingReferences(),
        ExistingReferences(),
        access,
    )
    return service, repository, storage, access, audit_events


def make_create_command(service_id, category_id):
    return CreateDocument(
        " Budget 2026 ", service_id, category_id, "budget.pdf",
        BytesIO(b"%PDF-1.7\nmunicipal budget"), date(2026, 1, 1), "REF-2026-001")


def test_create_verifies_object_before_activating_document():
    service, repository, storage, access, audit = make_service()
    actor_id, service_id, category_id = uuid4(), ServiceId(uuid4()), CategoryId(uuid4())

    document = service.create(make_create_command(service_id, category_id), actor_id)

    assert document.title == "Budget 2026"
    assert document.status.value == "active"
    assert len(document.versions) == 1
    assert document.versions[0].state is VersionState.AVAILABLE
    assert repository.get(document.id) is document
    assert len(storage.objects) == 1
    assert access.calls == [(actor_id, "document.create", service_id)]
    assert any(event[1] == "document.created" for event in audit)
    assert not repository.outbox


def test_add_version_preserves_old_file_and_advances_current_version():
    service, _repository, storage, _access, _audit = make_service()
    actor_id, service_id, category_id = uuid4(), ServiceId(uuid4()), CategoryId(uuid4())
    document = service.create(make_create_command(service_id, category_id), actor_id)
    first_version = document.current_version_id

    updated = service.add_version(document.id, BytesIO(b"%PDF-1.7\nrevised budget"),
        "budget-revised.pdf", actor_id, expected_version=1)

    assert len(updated.versions) == 2
    assert updated.current_version_id != first_version
    assert updated.versions[0].object_key.value in storage.objects
    assert updated.versions[1].object_key.value in storage.objects
    assert updated.versions[1].sequence == 2
    assert updated.aggregate_version == 2


def test_denied_create_is_audited_and_never_reaches_object_storage():
    service, repository, storage, _access, audit = make_service(access=AllowAllAccess(denied=True))
    actor_id, service_id, category_id = uuid4(), ServiceId(uuid4()), CategoryId(uuid4())

    with pytest.raises(DocumentNotFound):
        service.create(make_create_command(service_id, category_id), actor_id)

    assert not repository.documents
    assert storage.put_calls == 0
    assert any(event[1:3] == ("document.create", None) and event[4] == "denied" for event in audit)


def test_checksum_mismatch_keeps_reservation_pending_for_reconciliation():
    from municipal_assistant.documents.domain.errors import DependencyUnavailable

    service, repository, storage, _access, _audit = make_service(storage=MemoryStorage(corrupt_checksum=True))
    actor_id, service_id, category_id = uuid4(), ServiceId(uuid4()), CategoryId(uuid4())

    with pytest.raises(DependencyUnavailable):
        service.create(make_create_command(service_id, category_id), actor_id)

    assert len(repository.documents) == 1
    document = next(iter(repository.documents.values()))
    assert document.status.value == "pending"
    assert next(iter(repository.versions_by_id.values())).state is VersionState.PENDING
    assert len(storage.objects) == 1


def test_moving_a_document_requires_permission_on_source_and_target_services():
    service, _repository, _storage, access, audit = make_service()
    actor_id = uuid4()
    source, target = ServiceId(uuid4()), ServiceId(uuid4())
    category = CategoryId(uuid4())
    document = service.create(make_create_command(source, category), actor_id)
    access.calls.clear()

    updated = service.update(document.id, actor_id, title="Budget 2026", description=None,
        reference_number="REF-2026-001", document_date=date(2026, 1, 1), issuer=None, keywords=(),
        confidentiality_level=None, retention_code=None, service_id=target, category_id=category,
        expected_version=1)

    assert updated.service_id == target
    assert access.calls == [
        (actor_id, "document.metadata_update", source),
        (actor_id, "document.metadata_update", target),
    ]
    assert any(event[1] == "document.metadata_updated" for event in audit)

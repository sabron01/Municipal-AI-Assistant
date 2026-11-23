from datetime import datetime, timezone
from uuid import uuid4
import pytest

from municipal_assistant.documents.domain.entities import Document, DocumentStatus, DocumentVersion
from municipal_assistant.documents.domain.errors import ConcurrentModification, DocumentDeleted
from municipal_assistant.documents.domain.value_objects import (
    CategoryId, DocumentId, ObjectKey, ServiceId, Sha256, VersionId,
)


def make_document():
    now = datetime.now(timezone.utc)
    document_id, version_id = DocumentId(uuid4()), VersionId(uuid4())
    version = DocumentVersion(version_id, document_id, 1, ObjectKey(f"documents/{uuid4()}"),
        Sha256("a" * 64), 12, "application/pdf", "report.pdf", now, None)
    return Document(document_id, "Annual report", ServiceId(uuid4()), CategoryId(uuid4()),
        version_id, DocumentStatus.ACTIVE, now, None, now, reference_number="REF-1",
        document_date=now.date(), versions=[version])


def test_soft_delete_preserves_version_and_is_idempotent():
    document = make_document()
    document.soft_delete(datetime.now(timezone.utc), None)
    version_count = len(document.versions)
    document.soft_delete(datetime.now(timezone.utc), None)
    assert document.status is DocumentStatus.DELETED
    assert len(document.versions) == version_count == 1


def test_metadata_update_rejects_stale_aggregate_version():
    document = make_document()
    with pytest.raises(ConcurrentModification):
        document.update_metadata(title="Changed", description=None, reference_number="REF-1",
            document_date=document.document_date, issuer=None, keywords=(), confidentiality_level=None,
            retention_code=None, service_id=document.service_id, category_id=document.category_id,
            expected_version=99)


def test_deleted_document_cannot_receive_new_version():
    document = make_document()
    document.soft_delete(datetime.now(timezone.utc), None)
    source = document.versions[0]
    next_version = DocumentVersion(VersionId(uuid4()), document.id, 2,
        ObjectKey(f"documents/{uuid4()}"), source.sha256, 12, source.detected_mime_type,
        source.original_filename, datetime.now(timezone.utc), None)
    with pytest.raises(DocumentDeleted):
        document.add_version(next_version)


def test_sha256_is_normalized_and_checked():
    assert Sha256("A" * 64).value == "a" * 64
    with pytest.raises(ValueError):
        Sha256("not-a-checksum")

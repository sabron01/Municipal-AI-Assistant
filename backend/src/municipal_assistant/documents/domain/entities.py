from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID

from .errors import ConcurrentModification, DocumentDeleted, InvalidDocument
from .value_objects import CategoryId, DocumentId, ObjectKey, ServiceId, Sha256, VersionId


class DocumentStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    DELETED = "deleted"


class VersionState(StrEnum):
    PENDING = "pending"
    AVAILABLE = "available"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class DocumentVersion:
    id: VersionId
    document_id: DocumentId
    sequence: int
    object_key: ObjectKey
    sha256: Sha256
    size_bytes: int
    detected_mime_type: str
    original_filename: str
    created_at: datetime
    created_by: UUID | None
    state: VersionState = VersionState.AVAILABLE

    def __post_init__(self) -> None:
        if self.sequence < 1 or self.size_bytes < 1:
            raise InvalidDocument("Version sequence and size must be positive")
        if self.created_at.tzinfo is None:
            raise InvalidDocument("Timestamps must be timezone-aware")


@dataclass(slots=True)
class Document:
    id: DocumentId
    title: str
    service_id: ServiceId
    category_id: CategoryId
    current_version_id: VersionId
    status: DocumentStatus
    created_at: datetime
    created_by: UUID | None
    updated_at: datetime
    deleted_at: datetime | None = None
    deleted_by: UUID | None = None
    description: str | None = None
    reference_number: str | None = None
    aggregate_version: int = 1
    versions: list[DocumentVersion] = field(default_factory=list)

    def add_version(self, version: DocumentVersion) -> None:
        self._ensure_active()
        if version.document_id != self.id:
            raise InvalidDocument("Version belongs to another document")
        if any(existing.id == version.id or existing.sequence == version.sequence for existing in self.versions):
            raise InvalidDocument("Version id and sequence must be unique")
        if version.sequence != max((item.sequence for item in self.versions), default=0) + 1:
            raise InvalidDocument("Version sequence must be consecutive")
        if version.state is not VersionState.AVAILABLE:
            raise InvalidDocument("Only verified available versions can become current")
        self.versions.append(version)
        self.current_version_id = version.id
        self.updated_at = datetime.now(timezone.utc)
        self.aggregate_version += 1

    def soft_delete(self, at: datetime, actor_id: UUID | None) -> None:
        if at.tzinfo is None:
            raise InvalidDocument("Timestamps must be timezone-aware")
        if self.status is DocumentStatus.DELETED:
            return
        self.status = DocumentStatus.DELETED
        self.deleted_at = at
        self.deleted_by = actor_id
        self.updated_at = at
        self.aggregate_version += 1

    def update_metadata(self, *, title: str, description: str | None, reference_number: str | None,
                        service_id: ServiceId, category_id: CategoryId, expected_version: int) -> None:
        self._ensure_active()
        if self.aggregate_version != expected_version:
            raise ConcurrentModification("Document was changed by another request")
        if not title.strip():
            raise InvalidDocument("Title cannot be empty")
        self.title, self.description, self.reference_number = title.strip(), description, reference_number
        self.service_id, self.category_id = service_id, category_id
        self.aggregate_version += 1
        self.updated_at = datetime.now(timezone.utc)

    def _ensure_active(self) -> None:
        if self.status is not DocumentStatus.ACTIVE:
            raise DocumentDeleted("Document is deleted")

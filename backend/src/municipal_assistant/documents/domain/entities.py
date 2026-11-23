from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import StrEnum
from unicodedata import normalize as normalize_unicode
from uuid import UUID

from .errors import ConcurrentModification, DocumentDeleted, DocumentNotDeleted, InvalidDocument
from .value_objects import CategoryId, DocumentId, ObjectKey, ServiceId, Sha256, VersionId

MAX_KEYWORDS = 20
MAX_KEYWORD_LENGTH = 100


def normalize_reference(value: str) -> str:
    """Return the stable comparison key used for global reference uniqueness."""
    return normalize_unicode("NFKC", " ".join(value.split())).casefold()


def validate_metadata(*, title: str, reference_number: str | None, document_date: date | None,
                      issuer: str | None, keywords: tuple[str, ...],
                      confidentiality_level: str | None, retention_code: str | None) -> None:
    if not title or not title.strip() or len(title.strip()) > 300:
        raise InvalidDocument("Title must contain between 1 and 300 characters")
    if not reference_number or not reference_number.strip() or len(reference_number.strip()) > 200:
        raise InvalidDocument("Reference number must contain between 1 and 200 characters")
    if not isinstance(document_date, date):
        raise InvalidDocument("Document date is required")
    if issuer is not None and len(issuer.strip()) > 200:
        raise InvalidDocument("Issuer must contain at most 200 characters")
    if len(keywords) > MAX_KEYWORDS:
        raise InvalidDocument(f"At most {MAX_KEYWORDS} keywords are allowed")
    if any(not keyword.strip() or len(keyword.strip()) > MAX_KEYWORD_LENGTH for keyword in keywords):
        raise InvalidDocument("Each keyword must contain between 1 and 100 characters")
    for label, value in (("Confidentiality level", confidentiality_level), ("Retention code", retention_code)):
        if value is not None and len(value.strip()) > 100:
            raise InvalidDocument(f"{label} must contain at most 100 characters")


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
    document_date: date = field(kw_only=True)
    issuer: str | None = field(default=None, kw_only=True)
    keywords: tuple[str, ...] = field(default=(), kw_only=True)
    confidentiality_level: str | None = field(default=None, kw_only=True)
    retention_code: str | None = field(default=None, kw_only=True)
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

    def restore(self, at: datetime) -> None:
        if at.tzinfo is None:
            raise InvalidDocument("Timestamps must be timezone-aware")
        if self.status is not DocumentStatus.DELETED:
            raise DocumentNotDeleted("Document is not deleted")
        self.status = DocumentStatus.ACTIVE
        self.deleted_at = None
        self.deleted_by = None
        self.updated_at = at
        self.aggregate_version += 1

    def update_metadata(self, *, title: str, description: str | None, reference_number: str | None,
                        document_date: date, issuer: str | None, keywords: tuple[str, ...],
                        confidentiality_level: str | None, retention_code: str | None,
                        service_id: ServiceId, category_id: CategoryId, expected_version: int) -> None:
        self._ensure_active()
        if self.aggregate_version != expected_version:
            raise ConcurrentModification("Document was changed by another request")
        validate_metadata(title=title, reference_number=reference_number, document_date=document_date,
            issuer=issuer, keywords=keywords, confidentiality_level=confidentiality_level,
            retention_code=retention_code)
        self.title = title.strip()
        self.description = description
        self.reference_number = reference_number.strip()
        self.document_date = document_date
        self.issuer = issuer.strip() if issuer else None
        self.keywords = tuple(keyword.strip() for keyword in keywords)
        self.confidentiality_level = confidentiality_level.strip() if confidentiality_level else None
        self.retention_code = retention_code.strip() if retention_code else None
        self.service_id, self.category_id = service_id, category_id
        self.aggregate_version += 1
        self.updated_at = datetime.now(timezone.utc)

    def _ensure_active(self) -> None:
        if self.status is not DocumentStatus.ACTIVE:
            raise DocumentDeleted("Document is deleted")

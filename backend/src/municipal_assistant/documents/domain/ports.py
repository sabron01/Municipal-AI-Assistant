from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import BinaryIO, Protocol
from collections.abc import Sequence
from uuid import UUID

from .entities import Document, DocumentVersion
from .value_objects import CategoryId, DocumentId, ObjectKey, ServiceId, Sha256, VersionId


@dataclass(frozen=True, slots=True)
class DocumentQuery:
    service_id: ServiceId | None = None
    category_id: CategoryId | None = None
    cursor: str | None = None
    limit: int = 50

@dataclass(frozen=True, slots=True)
class StoredObjectReceipt:
    key: ObjectKey
    size_bytes: int
    sha256: Sha256

@dataclass(frozen=True, slots=True)
class StoredObjectMetadata:
    key: ObjectKey
    size_bytes: int
    sha256: Sha256
    content_type: str

@dataclass(frozen=True, slots=True)
class Page:
    items: Sequence[Document]
    next_cursor: str | None

class ReadableObject(Protocol):
    body: BinaryIO
    content_length: int
    content_type: str
    filename: str
    def close(self) -> None: ...

class DocumentRepository(Protocol):
    def get(self, document_id: DocumentId, *, include_deleted: bool = False) -> Document | None: ...
    def list(self, query: DocumentQuery) -> Page: ...
    def save(self, document: Document, *, expected_aggregate_version: int | None = None) -> None: ...
    def versions(self, document_id: DocumentId) -> Sequence[DocumentVersion]: ...
    def next_sequence(self, document_id: DocumentId) -> int: ...
    def reserve_version(self, version: DocumentVersion, *, expected_aggregate_version: int | None = None) -> None: ...
    def mark_version_available(self, version_id: VersionId) -> None: ...
    def complete_outbox(self, version_id: VersionId) -> None: ...
    def pending_uploads(self) -> Sequence[tuple[DocumentVersion, int | None]]: ...

class UnitOfWork(Protocol):
    documents: DocumentRepository
    audit: "DocumentAuditRepository"
    def __enter__(self) -> "UnitOfWork": ...
    def __exit__(self, exc_type: object, exc: object, tb: object) -> None: ...
    def commit(self) -> None: ...

class DocumentAuditRepository(Protocol):
    def record(self, *, actor_id: UUID, action: str, document_id: DocumentId | None,
               version_id: VersionId | None = None, outcome: str = "success") -> None: ...

class ObjectStorage(Protocol):
    def put(self, *, key: ObjectKey, body: BinaryIO, content_length: int,
            content_type: str, checksum_sha256: Sha256) -> StoredObjectReceipt: ...
    def open(self, key: ObjectKey, *, filename: str) -> ReadableObject: ...
    def head(self, key: ObjectKey) -> StoredObjectMetadata | None: ...
    def delete(self, key: ObjectKey) -> None: ...

class ServiceDirectory(Protocol):
    def exists(self, service_id: ServiceId) -> bool: ...
class CategoryDirectory(Protocol):
    def exists(self, category_id: CategoryId) -> bool: ...
class DocumentAccessPolicy(Protocol):
    def require(self, actor_id: UUID, action: str, service_id: ServiceId) -> None: ...
class UploadValidator(Protocol):
    def stage(self, body: BinaryIO, *, filename: str) -> "StagedUpload": ...

class StagedUpload(Protocol):
    body: BinaryIO
    filename: str
    mime_type: str
    size_bytes: int
    sha256: Sha256
    def close(self) -> None: ...

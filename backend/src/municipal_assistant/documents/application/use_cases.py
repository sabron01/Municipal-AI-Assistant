from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from typing import BinaryIO
from uuid import UUID, uuid4

from ..domain.entities import Document, DocumentStatus, DocumentVersion, VersionState, validate_metadata
from ..domain.errors import (ConcurrentModification, DependencyUnavailable, DocumentNotFound,
                             InvalidDocument, InvalidUpload)
from ..domain.ports import (CategoryDirectory, DocumentAccessPolicy, DocumentQuery, ObjectStorage,
                            ServiceDirectory, UnitOfWork, UploadValidator)
from ..domain.value_objects import CategoryId, DocumentId, ObjectKey, ServiceId, VersionId


@dataclass(frozen=True, slots=True)
class CreateDocument:
    title: str
    service_id: ServiceId
    category_id: CategoryId
    filename: str
    body: BinaryIO
    document_date: date
    reference_number: str
    description: str | None = None
    issuer: str | None = None
    keywords: tuple[str, ...] = ()
    confidentiality_level: str | None = None
    retention_code: str | None = None


class DocumentService:
    def __init__(self, uow_factory, storage: ObjectStorage, validator: UploadValidator,
                 service_directory: ServiceDirectory, category_directory: CategoryDirectory,
                 access: DocumentAccessPolicy):
        self.uow_factory, self.storage, self.validator = uow_factory, storage, validator
        self.service_directory, self.category_directory, self.access = service_directory, category_directory, access

    def create(self, command: CreateDocument, actor_id: UUID) -> Document:
        self._authorize(actor_id, "document.create", None, write=True, service_id=command.service_id)
        self._validate_references(command.service_id, command.category_id)
        validate_metadata(title=command.title, reference_number=command.reference_number,
            document_date=command.document_date, issuer=command.issuer, keywords=command.keywords,
            confidentiality_level=command.confidentiality_level, retention_code=command.retention_code)
        staged = self.validator.stage(command.body, filename=command.filename)
        document_id, version_id = DocumentId(uuid4()), VersionId(uuid4())
        key = ObjectKey(f"documents/{document_id.value}/{version_id.value}")
        try:
            with self.uow_factory() as uow:
                version = DocumentVersion(version_id, document_id, 1, key, staged.sha256,
                    staged.size_bytes, staged.mime_type, staged.filename, datetime.now(timezone.utc), actor_id,
                    state=VersionState.PENDING)
                document = Document(document_id, command.title.strip(), command.service_id, command.category_id,
                    version_id, DocumentStatus.PENDING, datetime.now(timezone.utc), actor_id,
                    datetime.now(timezone.utc), description=command.description,
                    reference_number=command.reference_number, document_date=command.document_date,
                    issuer=command.issuer, keywords=command.keywords,
                    confidentiality_level=command.confidentiality_level,
                    retention_code=command.retention_code, versions=[])
                uow.documents.save(document)
                uow.documents.reserve_version(version)
                uow.commit()
            receipt = self.storage.put(key=key, body=staged.body, content_length=staged.size_bytes,
                                       content_type=staged.mime_type, checksum_sha256=staged.sha256)
            stored = self.storage.head(key)
            if (receipt.sha256 != staged.sha256 or receipt.size_bytes != staged.size_bytes or stored is None
                    or stored.sha256 != staged.sha256 or stored.size_bytes != staged.size_bytes):
                raise DependencyUnavailable("Stored object verification failed")
            with self.uow_factory() as uow:
                document = self._get(uow, document_id, include_pending=True)
                uow.documents.mark_version_available(version_id)
                uow.documents.complete_outbox(version_id)
                document.status = DocumentStatus.ACTIVE
                document.versions.append(replace(version, state=VersionState.AVAILABLE))
                uow.documents.save(document)
                uow.audit.record(actor_id=actor_id, action="document.created", document_id=document_id,
                                 version_id=version_id)
                uow.commit()
            return document
        except Exception:
            # The DB reservation remains auditable and retryable; no object is deleted here.
            raise
        finally:
            staged.close()

    def add_version(self, document_id: DocumentId, body: BinaryIO, filename: str,
                    actor_id: UUID, expected_version: int) -> Document:
        with self.uow_factory() as uow:
            document = self._get(uow, document_id)
            self._authorize(actor_id, "document.version_add", document, write=True)
            if document.aggregate_version != expected_version:
                raise ConcurrentModification("Document version does not match If-Match")
            sequence = uow.documents.next_sequence(document_id)
        staged = self.validator.stage(body, filename=filename)
        version_id = VersionId(uuid4())
        key = ObjectKey(f"documents/{document_id.value}/{version_id.value}")
        try:
            version = DocumentVersion(version_id, document_id, sequence, key, staged.sha256,
                staged.size_bytes, staged.mime_type, staged.filename, datetime.now(timezone.utc), actor_id,
                state=VersionState.PENDING)
            with self.uow_factory() as uow:
                self._get(uow, document_id)
                uow.documents.reserve_version(version, expected_aggregate_version=expected_version)
                uow.commit()
            receipt = self.storage.put(key=key, body=staged.body, content_length=staged.size_bytes,
                content_type=staged.mime_type, checksum_sha256=staged.sha256)
            stored = self.storage.head(key)
            if (receipt.sha256 != staged.sha256 or receipt.size_bytes != staged.size_bytes or stored is None
                    or stored.sha256 != staged.sha256 or stored.size_bytes != staged.size_bytes):
                raise DependencyUnavailable("Stored object verification failed")
            with self.uow_factory() as uow:
                document = self._get(uow, document_id)
                self._authorize(actor_id, "document.version_add", document, write=True)
                if document.aggregate_version != expected_version:
                    raise ConcurrentModification("Document changed during upload")
                uow.documents.mark_version_available(version_id)
                uow.documents.complete_outbox(version_id)
                version = replace(version, state=VersionState.AVAILABLE)
                document.add_version(version)
                uow.documents.save(document, expected_aggregate_version=expected_version)
                uow.audit.record(actor_id=actor_id, action="document.version_added", document_id=document_id,
                                 version_id=version_id)
                uow.commit()
            return document
        finally:
            staged.close()

    def get(self, document_id: DocumentId, actor_id: UUID) -> Document:
        with self.uow_factory() as uow:
            document = self._get(uow, document_id)
            self._authorize(actor_id, "document.read", document, write=False)
            uow.audit.record(actor_id=actor_id, action="document.read", document_id=document_id)
            uow.commit()
            return document

    def list(self, query: DocumentQuery, actor_id: UUID):
        with self.uow_factory() as uow:
            page = uow.documents.list(query)
            visible = []
            for item in page.items:
                try:
                    self._authorize(actor_id, "document.list", item, write=False)
                except DocumentNotFound:
                    continue
                visible.append(item)
                uow.audit.record(actor_id=actor_id, action="document.listed", document_id=item.id)
            uow.commit()
            return replace(page, items=visible)

    def versions(self, document_id: DocumentId, actor_id: UUID):
        document = self.get(document_id, actor_id)
        with self.uow_factory() as uow:
            items = uow.documents.versions(document_id)
            for item in items:
                uow.audit.record(actor_id=actor_id, action="document.versions_listed",
                    document_id=document_id, version_id=item.id)
            uow.commit()
            return items

    def download(self, document_id: DocumentId, actor_id: UUID, version_id: VersionId | None = None):
        document = self.get(document_id, actor_id)
        versions = self.versions(document_id, actor_id)
        selected = next((v for v in versions if v.id == (version_id or document.current_version_id)), None)
        if selected is None:
            raise DocumentNotFound("Document version was not found")
        readable = self.storage.open(selected.object_key, filename=selected.original_filename)
        try:
            with self.uow_factory() as uow:
                uow.audit.record(actor_id=actor_id, action="document.downloaded",
                    document_id=document_id, version_id=selected.id)
                uow.commit()
            return readable
        except Exception:
            readable.close()
            raise

    def update(self, document_id: DocumentId, actor_id: UUID, *, title: str, description: str | None,
               reference_number: str, document_date: date, issuer: str | None, keywords: tuple[str, ...],
               confidentiality_level: str | None, retention_code: str | None, service_id: ServiceId,
               category_id: CategoryId, expected_version: int) -> Document:
        with self.uow_factory() as uow:
            document = self._get(uow, document_id)
            self._authorize(actor_id, "document.metadata_update", document, write=True)
            if service_id != document.service_id:
                self._authorize(actor_id, "document.metadata_update", None, write=True,
                                service_id=service_id)
            self._validate_references(service_id, category_id)
            document.update_metadata(title=title, description=description, reference_number=reference_number,
                                     document_date=document_date, issuer=issuer, keywords=keywords,
                                     confidentiality_level=confidentiality_level, retention_code=retention_code,
                                     service_id=service_id, category_id=category_id,
                                     expected_version=expected_version)
            uow.documents.save(document, expected_aggregate_version=expected_version)
            uow.audit.record(actor_id=actor_id, action="document.metadata_updated", document_id=document_id)
            uow.commit()
            return document

    def soft_delete(self, document_id: DocumentId, actor_id: UUID, expected_version: int) -> None:
        with self.uow_factory() as uow:
            document = self._get(uow, document_id)
            self._authorize(actor_id, "document.soft_delete", document, write=True)
            if document.aggregate_version != expected_version:
                raise ConcurrentModification("Document version does not match If-Match")
            document.soft_delete(datetime.now(timezone.utc), actor_id)
            uow.documents.save(document, expected_aggregate_version=expected_version)
            uow.audit.record(actor_id=actor_id, action="document.soft_deleted", document_id=document_id)
            uow.commit()

    def reconcile_pending_uploads(self) -> int:
        """Idempotently finish committed reservations whose object was already uploaded."""
        with self.uow_factory() as uow:
            pending = uow.documents.pending_uploads()
        completed = 0
        for version, expected_version in pending:
            stored = self.storage.head(version.object_key)
            if stored is None or stored.sha256 != version.sha256 or stored.size_bytes != version.size_bytes:
                continue
            with self.uow_factory() as uow:
                document = uow.documents.get(version.document_id, include_deleted=True)
                if document is None:
                    continue
                uow.documents.mark_version_available(version.id)
                uow.documents.complete_outbox(version.id)
                if document.status is DocumentStatus.PENDING:
                    expected_document_version = document.aggregate_version
                    document.status = DocumentStatus.ACTIVE
                    document.versions.append(replace(version, state=VersionState.AVAILABLE))
                elif document.status is DocumentStatus.ACTIVE:
                    if (document.aggregate_version != expected_version
                            or version.sequence != uow.documents.next_sequence(version.document_id) - 1):
                        continue
                    expected_document_version = document.aggregate_version
                    document.add_version(replace(version, state=VersionState.AVAILABLE))
                else:
                    continue
                if document.status is DocumentStatus.ACTIVE and version.sequence > 1:
                    uow.documents.save(document, expected_aggregate_version=expected_document_version)
                else:
                    uow.documents.save(document)
                uow.commit()
                completed += 1
        return completed

    def _validate_references(self, service_id: ServiceId, category_id: CategoryId) -> None:
        if not self.service_directory.exists(service_id) or not self.category_directory.exists(category_id):
            raise InvalidDocument("Unknown service or category")

    def _authorize(self, actor_id: UUID, action: str, document: Document | None, *, write: bool,
                   service_id: ServiceId | None = None) -> None:
        try:
            scoped_service = document.service_id if document is not None else service_id
            if scoped_service is None:
                raise AccessPolicyUnavailable("A service scope is required for authorization")
            require = getattr(self.access, "require", None)
            if require is not None:
                require(actor_id, action, scoped_service)
            elif action in {"document.read", "document.list"} and document is not None:
                self.access.require_read(actor_id, document)
            else:
                self.access.require_write(actor_id, document)
        except Exception:
            with self.uow_factory() as audit_uow:
                audit_uow.audit.record(actor_id=actor_id, action=action,
                    document_id=document.id if document else None, outcome="denied")
                audit_uow.commit()
            raise

    @staticmethod
    def _get(uow, document_id: DocumentId, *, include_pending: bool = False) -> Document:
        document = uow.documents.get(document_id, include_deleted=include_pending)
        if document is None:
            raise DocumentNotFound("Document was not found")
        return document

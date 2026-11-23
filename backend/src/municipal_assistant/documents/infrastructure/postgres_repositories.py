import base64
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import create_engine, select, update, func, and_, or_
from sqlalchemy.orm import Session, sessionmaker, selectinload

from ..domain.entities import Document, DocumentStatus, DocumentVersion, VersionState, normalize_reference
from ..domain.errors import (ConcurrentModification, DependencyUnavailable, InvalidPageCursor, ReferenceConflict)
from ..domain.ports import DocumentQuery, Page
from ..domain.value_objects import CategoryId, DocumentId, ObjectKey, ServiceId, Sha256, VersionId
from sqlalchemy.exc import IntegrityError
from .sqlalchemy_models import Base, DocumentAuditRow, DocumentRow, DocumentVersionRow, OutboxRow


def make_session_factory(database_url: str):
    engine = create_engine(database_url, pool_pre_ping=True)
    return sessionmaker(engine, expire_on_commit=False), engine


class PostgresUnitOfWork:
    def __init__(self, factory):
        self.factory = factory
        self.session: Session | None = None
        self.documents = None
        self.audit = None

    def __enter__(self):
        self.session = self.factory()
        self.documents = PostgresDocumentRepository(self.session)
        self.audit = PostgresDocumentAuditRepository(self.session)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.session is not None:
            if exc_type:
                self.session.rollback()
            self.session.close()

    def commit(self):
        assert self.session is not None
        self.session.commit()


class PostgresDocumentRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, document_id: DocumentId, *, include_deleted: bool = False) -> Document | None:
        stmt = select(DocumentRow).options(selectinload(DocumentRow.versions)).where(DocumentRow.id == document_id.value)
        if not include_deleted:
            stmt = stmt.where(DocumentRow.status == DocumentStatus.ACTIVE.value)
        row = self.session.scalar(stmt.with_for_update())
        return _to_domain(row) if row else None

    def list(self, query: DocumentQuery) -> Page:
        if not 1 <= query.limit <= 100:
            raise ValueError("Page limit must be between 1 and 100")
        stmt = select(DocumentRow).options(selectinload(DocumentRow.versions)).where(
            DocumentRow.status == DocumentStatus.ACTIVE.value)
        if query.service_id:
            stmt = stmt.where(DocumentRow.service_id == query.service_id.value)
        if query.category_id:
            stmt = stmt.where(DocumentRow.category_id == query.category_id.value)
        if query.cursor:
            created_text, id_text = _decode_cursor(query.cursor)
            created = datetime.fromisoformat(created_text)
            doc_id = UUID(id_text)
            stmt = stmt.where(or_(DocumentRow.created_at < created,
                and_(DocumentRow.created_at == created, DocumentRow.id < doc_id)))
        stmt = stmt.order_by(DocumentRow.created_at.desc(), DocumentRow.id.desc()).limit(query.limit + 1)
        rows = list(self.session.scalars(stmt))
        has_more = len(rows) > query.limit
        rows = rows[:query.limit]
        next_cursor = _encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None
        return Page(tuple(_to_domain(row) for row in rows), next_cursor)

    def purge(self, document_id: DocumentId) -> None:
        from sqlalchemy import delete as sa_delete
        version_ids = select(DocumentVersionRow.id).where(DocumentVersionRow.document_id == document_id.value)
        self.session.execute(sa_delete(OutboxRow).where(OutboxRow.version_id.in_(version_ids)))
        self.session.execute(sa_delete(DocumentVersionRow).where(DocumentVersionRow.document_id == document_id.value))
        self.session.execute(sa_delete(DocumentAuditRow).where(DocumentAuditRow.document_id == document_id.value))
        self.session.execute(sa_delete(DocumentRow).where(DocumentRow.id == document_id.value))
        self.session.flush()

    def next_sequence(self, document_id: DocumentId) -> int:
        self.session.scalar(select(DocumentRow.id).where(DocumentRow.id == document_id.value).with_for_update())
        value = self.session.scalar(select(func.max(DocumentVersionRow.sequence)).where(
            DocumentVersionRow.document_id == document_id.value))
        return (value or 0) + 1
        self.session.scalar(select(DocumentRow.id).where(DocumentRow.id == document_id.value).with_for_update())
        value = self.session.scalar(select(func.max(DocumentVersionRow.sequence)).where(
            DocumentVersionRow.document_id == document_id.value))
        return (value or 0) + 1

    def versions(self, document_id: DocumentId):
        rows = self.session.scalars(select(DocumentVersionRow).where(
            DocumentVersionRow.document_id == document_id.value,
            DocumentVersionRow.state == VersionState.AVAILABLE.value).order_by(DocumentVersionRow.sequence))
        return tuple(_version_to_domain(row) for row in rows)

    def reserve_version(self, version: DocumentVersion, *, expected_aggregate_version: int | None = None) -> None:
        if expected_aggregate_version is not None:
            aggregate_version = self.session.scalar(select(DocumentRow.aggregate_version).where(
                DocumentRow.id == version.document_id.value).with_for_update())
            if aggregate_version != expected_aggregate_version:
                raise ConcurrentModification("Document changed before the upload could be reserved")
            pending_id = self.session.scalar(select(DocumentVersionRow.id).where(
                DocumentVersionRow.document_id == version.document_id.value,
                DocumentVersionRow.state == VersionState.PENDING.value).limit(1))
            if pending_id is not None:
                raise ConcurrentModification("Another document upload is still pending")
        self.session.add(DocumentVersionRow(id=version.id.value, document_id=version.document_id.value,
            sequence=version.sequence, object_key=version.object_key.value, sha256=version.sha256.value,
            size_bytes=version.size_bytes, detected_mime_type=version.detected_mime_type,
            original_filename=version.original_filename, state=VersionState.PENDING.value,
            created_at=version.created_at, created_by=version.created_by,
            expected_aggregate_version=expected_aggregate_version))
        self.session.add(OutboxRow(version_id=version.id.value, event_type="document.object.verify"))

    def mark_version_available(self, version_id: VersionId) -> None:
        row = self.session.get(DocumentVersionRow, version_id.value)
        if row is None or row.state != VersionState.PENDING.value:
            raise DependencyUnavailable("Pending document upload reservation is missing")
        row.state = VersionState.AVAILABLE.value

    def pending_uploads(self):
        rows = self.session.scalars(select(DocumentVersionRow).where(
            DocumentVersionRow.state == VersionState.PENDING.value).order_by(DocumentVersionRow.created_at))
        return tuple((_version_to_domain(row), row.expected_aggregate_version) for row in rows)

    def complete_outbox(self, version_id: VersionId) -> None:
        event = self.session.scalar(select(OutboxRow).where(OutboxRow.version_id == version_id.value))
        if event is not None:
            event.completed = True

    def save(self, document: Document, *, expected_aggregate_version: int | None = None) -> None:
        try:
            self._save(document, expected_aggregate_version=expected_aggregate_version)
        except IntegrityError as exc:
            if _is_reference_conflict(exc):
                raise ReferenceConflict("A document with this reference number already exists") from exc
            raise

    def _save(self, document: Document, *, expected_aggregate_version: int | None = None) -> None:
        row = self.session.get(DocumentRow, document.id.value)
        if row is None:
            row = DocumentRow(id=document.id.value, title=document.title, service_id=document.service_id.value,
                category_id=document.category_id.value, current_version_id=document.current_version_id.value,
                status=document.status.value, description=document.description, reference_number=document.reference_number,
                reference_normalized=normalize_reference(document.reference_number),
                document_date=document.document_date, issuer=document.issuer, keywords=list(document.keywords),
                confidentiality_level=document.confidentiality_level, retention_code=document.retention_code,
                created_at=document.created_at, created_by=document.created_by, updated_at=document.updated_at,
                deleted_at=document.deleted_at, deleted_by=document.deleted_by,
                aggregate_version=document.aggregate_version)
            self.session.add(row)
            self.session.flush()
        else:
            expected = expected_aggregate_version
            if expected is not None:
                result = self.session.execute(update(DocumentRow).where(DocumentRow.id == document.id.value,
                    DocumentRow.aggregate_version == expected).values(
                    title=document.title, service_id=document.service_id.value, category_id=document.category_id.value,
                    current_version_id=document.current_version_id.value, status=document.status.value,
                    description=document.description, reference_number=document.reference_number,
                    reference_normalized=normalize_reference(document.reference_number),
                    document_date=document.document_date, issuer=document.issuer, keywords=list(document.keywords),
                    confidentiality_level=document.confidentiality_level, retention_code=document.retention_code,
                    updated_at=document.updated_at, deleted_at=document.deleted_at, deleted_by=document.deleted_by,
                    aggregate_version=document.aggregate_version).execution_options(synchronize_session=False))
                if result.rowcount != 1:
                    raise ConcurrentModification("Document changed concurrently")
                self.session.expire(row)
            else:
                row.title, row.service_id, row.category_id = document.title, document.service_id.value, document.category_id.value
                row.current_version_id, row.status = document.current_version_id.value, document.status.value
                row.description, row.reference_number = document.description, document.reference_number
                row.reference_normalized = normalize_reference(document.reference_number)
                row.document_date, row.issuer = document.document_date, document.issuer
                row.keywords, row.confidentiality_level = list(document.keywords), document.confidentiality_level
                row.retention_code = document.retention_code
                row.updated_at, row.deleted_at, row.deleted_by = document.updated_at, document.deleted_at, document.deleted_by
                row.aggregate_version = document.aggregate_version
        existing = set(self.session.scalars(select(DocumentVersionRow.id).where(
            DocumentVersionRow.document_id == document.id.value)))
        for version in document.versions:
            if version.id.value in existing:
                continue
            version_row = DocumentVersionRow(id=version.id.value, document_id=document.id.value,
                sequence=version.sequence, object_key=version.object_key.value, sha256=version.sha256.value,
                size_bytes=version.size_bytes, detected_mime_type=version.detected_mime_type,
                original_filename=version.original_filename, state=version.state.value,
                created_at=version.created_at, created_by=version.created_by)
            self.session.add(version_row)
            self.session.add(OutboxRow(version_id=version.id.value, event_type="document.object.verify"))


class PostgresDocumentAuditRepository:
    def __init__(self, session: Session): self.session = session
    def record(self, *, actor_id: UUID, action: str, document_id: DocumentId | None,
               version_id: VersionId | None = None, outcome: str = "success") -> None:
        self.session.add(DocumentAuditRow(actor_id=actor_id, action=action,
            document_id=document_id.value if document_id else None,
            version_id=version_id.value if version_id else None, outcome=outcome))


def _version_to_domain(row: DocumentVersionRow) -> DocumentVersion:
    return DocumentVersion(VersionId(row.id), DocumentId(row.document_id), row.sequence,
        ObjectKey(row.object_key), Sha256(row.sha256), row.size_bytes, row.detected_mime_type,
        row.original_filename, row.created_at, row.created_by, VersionState(row.state))


def _to_domain(row: DocumentRow) -> Document:
    versions = [_version_to_domain(v) for v in row.versions if v.state == VersionState.AVAILABLE.value]
    return Document(DocumentId(row.id), row.title, ServiceId(row.service_id), CategoryId(row.category_id),
        VersionId(row.current_version_id), DocumentStatus(row.status), row.created_at, row.created_by,
        row.updated_at, row.deleted_at, row.deleted_by, row.description, row.reference_number,
        document_date=row.document_date, issuer=row.issuer, keywords=tuple(row.keywords or ()),
        confidentiality_level=row.confidentiality_level, retention_code=row.retention_code,
        aggregate_version=row.aggregate_version, versions=versions)


def _encode_cursor(created_at: datetime, document_id: UUID) -> str:
    raw = f"{created_at.isoformat()}|{document_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _is_reference_conflict(exc: IntegrityError) -> bool:
    diag = getattr(exc.orig, "diag", None)
    name = getattr(diag, "constraint_name", None)
    if name == "uq_documents_reference_normalized":
        return True
    return "reference_normalized" in str(exc.orig)
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        created_at, document_id = raw.split("|", 1)
        datetime.fromisoformat(created_at); UUID(document_id)
        return created_at, document_id
    except (ValueError, UnicodeDecodeError) as exc:
        raise InvalidPageCursor("Invalid pagination cursor") from exc

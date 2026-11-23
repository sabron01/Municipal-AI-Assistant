from datetime import date, datetime
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint,
                        Index, Integer, String, Text, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from uuid import uuid4


class Base(DeclarativeBase): pass


class DocumentRow(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("status IN ('pending','active','deleted')", name="ck_documents_status"),
        CheckConstraint("aggregate_version > 0", name="ck_documents_aggregate_version"),
        ForeignKeyConstraint(["id", "current_version_id"], ["documents.document_versions.document_id",
            "documents.document_versions.id"], name="fk_documents_current_version", deferrable=True,
            initially="DEFERRED", use_alter=True),
        Index("ix_documents_service_created", "service_id", text("created_at DESC"), text("id DESC")),
        Index("ix_documents_category_created", "category_id", text("created_at DESC"), text("id DESC")),
        Index("ix_documents_active", "created_at", "id", postgresql_where=text("status = 'active'")),
        Index("uq_documents_reference_normalized", "reference_normalized", unique=True),
        {"schema": "documents"},
    )
    id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    service_id: Mapped[object] = mapped_column(UUID(as_uuid=True), nullable=False)
    category_id: Mapped[object] = mapped_column(UUID(as_uuid=True), nullable=False)
    current_version_id: Mapped[object] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    description: Mapped[str | None] = mapped_column(String(5000))
    reference_number: Mapped[str] = mapped_column(String(200), nullable=False)
    reference_normalized: Mapped[str] = mapped_column(String(200), nullable=False)
    document_date: Mapped[date] = mapped_column(Date, nullable=False)
    issuer: Mapped[str | None] = mapped_column(String(200))
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String(100)), nullable=False,
        server_default=text("'{}'::varchar[]"))
    confidentiality_level: Mapped[str | None] = mapped_column(String(100))
    retention_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by: Mapped[object | None] = mapped_column(UUID(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[object | None] = mapped_column(UUID(as_uuid=True))
    aggregate_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    versions: Mapped[list["DocumentVersionRow"]] = relationship(back_populates="document",
        cascade="all, delete-orphan", foreign_keys="DocumentVersionRow.document_id", lazy="selectin")


class DocumentVersionRow(Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "sequence", name="uq_document_version_sequence"),
        UniqueConstraint("document_id", "id", name="uq_document_version_document_id"),
        UniqueConstraint("object_key", name="uq_document_version_object_key"),
        CheckConstraint("sequence > 0", name="ck_document_version_sequence"),
        CheckConstraint("size_bytes > 0", name="ck_document_version_size"),
        CheckConstraint("state IN ('pending','available','failed')", name="ck_document_version_state"),
        Index("ix_document_versions_document_sequence", "document_id", text("sequence DESC")),
        Index("uq_document_versions_one_pending_per_document", "document_id", unique=True,
              postgresql_where=text("state = 'pending'")),
        {"schema": "documents"},
    )
    id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[object] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.documents.id",
        ondelete="RESTRICT", name="fk_document_versions_document"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    detected_mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)
    expected_aggregate_version: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by: Mapped[object | None] = mapped_column(UUID(as_uuid=True))
    document: Mapped[DocumentRow] = relationship(back_populates="versions", foreign_keys=[document_id])


class OutboxRow(Base):
    __tablename__ = "document_outbox"
    __table_args__ = {"schema": "documents"}
    id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    version_id: Mapped[object] = mapped_column(UUID(as_uuid=True), ForeignKey(
        "documents.document_versions.id", ondelete="RESTRICT"), nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DocumentAuditRow(Base):
    __tablename__ = "document_audit"
    __table_args__ = (Index("ix_document_audit_doc_created", "document_id", "created_at"),
                      {"schema": "documents"})
    id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[object | None] = mapped_column(UUID(as_uuid=True), ForeignKey(
        "documents.documents.id", ondelete="RESTRICT"))
    version_id: Mapped[object | None] = mapped_column(UUID(as_uuid=True), ForeignKey(
        "documents.document_versions.id", ondelete="RESTRICT"))
    actor_id: Mapped[object] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False, default="success")
    request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

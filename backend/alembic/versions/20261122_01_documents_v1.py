"""Initial Documents v1 schema.

Revision ID: 20261122_01
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261122_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS documents")
    op.create_table("documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("description", sa.String(length=5000)),
        sa.Column("reference_number", sa.String(length=200)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True)),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.CheckConstraint("status IN ('pending','active','deleted')", name="ck_documents_status"),
        sa.CheckConstraint("aggregate_version > 0", name="ck_documents_aggregate_version"),
        sa.PrimaryKeyConstraint("id"), schema="documents")
    op.create_table("document_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True)),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("detected_mime_type", sa.String(length=255), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128)),
        sa.Column("expected_aggregate_version", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True)),
        sa.CheckConstraint("sequence > 0", name="ck_document_version_sequence"),
        sa.CheckConstraint("size_bytes > 0", name="ck_document_version_size"),
        sa.CheckConstraint("state IN ('pending','available','failed')", name="ck_document_version_state"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.documents.id"], ondelete="RESTRICT",
                                name="fk_document_versions_document"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "sequence", name="uq_document_version_sequence"),
        sa.UniqueConstraint("document_id", "id", name="uq_document_version_document_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_document_versions_idempotency_key"),
        sa.UniqueConstraint("object_key", name="uq_document_version_object_key"), schema="documents")
    op.create_foreign_key("fk_documents_current_version", "documents", "document_versions",
        ["id", "current_version_id"], ["document_id", "id"], source_schema="documents",
        referent_schema="documents", deferrable=True, initially="DEFERRED")
    op.create_index("ix_documents_service_created", "documents", ["service_id", sa.text("created_at DESC"), sa.text("id DESC")], schema="documents")
    op.create_index("ix_documents_category_created", "documents", ["category_id", sa.text("created_at DESC"), sa.text("id DESC")], schema="documents")
    op.create_index("ix_documents_active", "documents", ["created_at", "id"], schema="documents",
                    postgresql_where=sa.text("status = 'active'"))
    op.create_index("ix_document_versions_document_sequence", "document_versions", ["document_id", sa.text("sequence DESC")], schema="documents")
    op.create_table("document_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["version_id"], ["documents.document_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("version_id"), schema="documents")
    op.create_table("document_audit",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True)),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("request_id", sa.String(length=64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["version_id"], ["documents.document_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), schema="documents")
    op.create_index("ix_document_audit_doc_created", "document_audit", ["document_id", "created_at"], schema="documents")


def downgrade():
    op.drop_index("ix_document_audit_doc_created", table_name="document_audit", schema="documents")
    op.drop_table("document_audit", schema="documents")
    op.drop_table("document_outbox", schema="documents")
    op.drop_index("ix_document_versions_document_sequence", table_name="document_versions", schema="documents")
    op.drop_index("ix_documents_active", table_name="documents", schema="documents")
    op.drop_index("ix_documents_category_created", table_name="documents", schema="documents")
    op.drop_index("ix_documents_service_created", table_name="documents", schema="documents")
    op.drop_constraint("fk_documents_current_version", "documents", schema="documents", type_="foreignkey")
    op.drop_table("document_versions", schema="documents")
    op.drop_table("documents", schema="documents")
    op.execute("DROP SCHEMA documents")

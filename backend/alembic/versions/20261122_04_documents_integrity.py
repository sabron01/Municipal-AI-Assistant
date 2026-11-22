"""Align document nullability with the domain model.

Revision ID: 20261122_04
Revises: 20261122_03
"""
from alembic import op
import sqlalchemy as sa

revision = "20261122_04"
down_revision = "20261122_03"
branch_labels = None
depends_on = None


def upgrade():
    # A version must always belong to its document. Refuse to hide inconsistent
    # legacy rows if this migration is applied to a non-empty database.
    connection = op.get_bind()
    orphaned_versions = connection.execute(sa.text(
        "SELECT count(*) FROM documents.document_versions WHERE document_id IS NULL"
    )).scalar_one()
    if orphaned_versions:
        raise RuntimeError(
            f"Cannot require document_id: {orphaned_versions} document version row(s) are orphaned"
        )

    op.alter_column("document_versions", "document_id", schema="documents",
                    existing_type=sa.dialects.postgresql.UUID(as_uuid=True), nullable=False)
    op.alter_column("document_audit", "document_id", schema="documents",
                    existing_type=sa.dialects.postgresql.UUID(as_uuid=True), nullable=True)


def downgrade():
    # Keep nullable audit document references; audit rows can legitimately cover
    # denied requests that had no resolved document.
    op.alter_column("document_versions", "document_id", schema="documents",
                    existing_type=sa.dialects.postgresql.UUID(as_uuid=True), nullable=True)

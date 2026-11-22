"""Serialize pending version uploads per document.

Revision ID: 20261122_05
Revises: 20261122_04
"""
from alembic import op
import sqlalchemy as sa

revision = "20261122_05"
down_revision = "20261122_04"
branch_labels = None
depends_on = None


def upgrade():
    duplicate_reservations = op.get_bind().execute(sa.text(
        "SELECT count(*) FROM ("
        "SELECT document_id FROM documents.document_versions "
        "WHERE state = 'pending' GROUP BY document_id HAVING count(*) > 1"
        ") AS duplicate_documents"
    )).scalar_one()
    if duplicate_reservations:
        raise RuntimeError(
            f"Cannot serialize uploads: {duplicate_reservations} document(s) have multiple pending versions"
        )
    op.create_index(
        "uq_document_versions_one_pending_per_document",
        "document_versions",
        ["document_id"],
        unique=True,
        schema="documents",
        postgresql_where=sa.text("state = 'pending'"),
    )


def downgrade():
    op.drop_index(
        "uq_document_versions_one_pending_per_document",
        table_name="document_versions",
        schema="documents",
    )

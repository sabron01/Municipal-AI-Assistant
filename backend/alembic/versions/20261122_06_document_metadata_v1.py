"""Document business metadata: reference uniqueness, date, issuer, keywords, confidentiality, retention.

Revision ID: 20261122_06
Revises: 20261122_05
"""
from alembic import op
import sqlalchemy as sa
import unicodedata
from sqlalchemy.dialects import postgresql

revision = "20261122_06"
down_revision = "20261122_05"
branch_labels = None
depends_on = None


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", " ".join(value.split())).casefold()


def upgrade():
    op.add_column("documents", sa.Column("reference_normalized", sa.String(length=200)),
                  schema="documents")
    op.add_column("documents", sa.Column("document_date", sa.Date()), schema="documents")
    op.add_column("documents", sa.Column("issuer", sa.String(length=200)), schema="documents")
    op.add_column("documents", sa.Column("keywords", postgresql.ARRAY(sa.String(length=100)),
                  nullable=False, server_default=sa.text("'{}'::varchar[]")), schema="documents")
    op.add_column("documents", sa.Column("confidentiality_level", sa.String(length=100)),
                  schema="documents")
    op.add_column("documents", sa.Column("retention_code", sa.String(length=100)), schema="documents")

    bind = op.get_bind()
    incomplete = bind.scalar(sa.text(
        "SELECT count(*) FROM documents.documents "
        "WHERE reference_number IS NULL OR document_date IS NULL"
    ))
    if incomplete:
        raise RuntimeError(
            "Cannot apply 20261122_06: existing documents must be given a "
            "reference_number and document_date first."
        )

    for row_id, reference in bind.execute(
            sa.text("SELECT id, reference_number FROM documents.documents WHERE reference_number IS NOT NULL")):
        bind.execute(sa.text(
            "UPDATE documents.documents SET reference_normalized = :value WHERE id = :id"),
            {"value": _normalize(reference), "id": row_id})

    duplicates = bind.execute(sa.text(
        "SELECT reference_normalized FROM documents.documents "
        "GROUP BY reference_normalized HAVING count(*) > 1"
    )).fetchall()
    if duplicates:
        raise RuntimeError(
            "Cannot apply 20261122_06: duplicate reference numbers exist: "
            + ", ".join(str(item[0]) for item in duplicates)
        )

    op.alter_column("documents", "reference_number", existing_type=sa.String(length=200),
                    nullable=False, schema="documents")
    op.alter_column("documents", "reference_normalized", existing_type=sa.String(length=200),
                    nullable=False, schema="documents")
    op.alter_column("documents", "document_date", existing_type=sa.Date(), nullable=False,
                    schema="documents")
    op.create_index("uq_documents_reference_normalized", "documents", ["reference_normalized"],
                    unique=True, schema="documents")


def downgrade():
    op.drop_index("uq_documents_reference_normalized", table_name="documents", schema="documents")
    op.drop_column("documents", "retention_code", schema="documents")
    op.drop_column("documents", "confidentiality_level", schema="documents")
    op.drop_column("documents", "keywords", schema="documents")
    op.drop_column("documents", "issuer", schema="documents")
    op.drop_column("documents", "document_date", schema="documents")
    op.drop_column("documents", "reference_normalized", schema="documents")
    op.alter_column("documents", "reference_number", existing_type=sa.String(length=200),
                    nullable=True, schema="documents")
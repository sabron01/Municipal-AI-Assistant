"""Administration-owned direction, service and category catalogs.

Revision ID: 20261122_03
Revises: 20261122_02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261122_03"
down_revision = "20261122_02"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS administration")
    op.create_table("directions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("normalized_name", sa.String(length=600), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"), schema="administration")
    op.create_index("uq_directions_normalized_name", "directions", ["normalized_name"],
        unique=True, schema="administration")

    op.create_table("services",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("direction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("normalized_name", sa.String(length=600), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["direction_id"], ["administration.directions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), schema="administration")
    op.create_index("uq_services_direction_normalized_name", "services",
        ["direction_id", "normalized_name"], unique=True, schema="administration")
    op.create_index("ix_services_direction_name", "services", ["direction_id", "name"], schema="administration")

    op.create_table("categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True)),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("normalized_name", sa.String(length=600), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["administration.categories.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), schema="administration")
    op.create_index("uq_categories_root_normalized_name", "categories", ["normalized_name"],
        unique=True, schema="administration", postgresql_where=sa.text("parent_id IS NULL"))
    op.create_index("uq_categories_child_normalized_name", "categories", ["parent_id", "normalized_name"],
        unique=True, schema="administration", postgresql_where=sa.text("parent_id IS NOT NULL"))

    op.create_table("catalog_audit",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"), schema="administration")
    op.create_index("ix_catalog_audit_created", "catalog_audit", ["created_at"], schema="administration")


def downgrade():
    op.drop_index("ix_catalog_audit_created", table_name="catalog_audit", schema="administration")
    op.drop_table("catalog_audit", schema="administration")
    op.drop_index("uq_categories_child_normalized_name", table_name="categories", schema="administration")
    op.drop_index("uq_categories_root_normalized_name", table_name="categories", schema="administration")
    op.drop_table("categories", schema="administration")
    op.drop_index("ix_services_direction_name", table_name="services", schema="administration")
    op.drop_index("uq_services_direction_normalized_name", table_name="services", schema="administration")
    op.drop_table("services", schema="administration")
    op.drop_index("uq_directions_normalized_name", table_name="directions", schema="administration")
    op.drop_table("directions", schema="administration")
    op.execute("DROP SCHEMA IF EXISTS administration")

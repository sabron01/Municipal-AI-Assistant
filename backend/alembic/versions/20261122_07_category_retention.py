"""Administration category retention period.

Revision ID: 20261122_07
Revises: 20261122_06
"""
from alembic import op
import sqlalchemy as sa

revision = "20261122_07"
down_revision = "20261122_06"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("categories", sa.Column("retention_years", sa.Integer()),
                  schema="administration")


def downgrade():
    op.drop_column("categories", "retention_years", schema="administration")
"""Document restore and purge permissions.

Revision ID: 20261122_08
Revises: 20261122_07
"""
from alembic import op
import sqlalchemy as sa

revision = "20261122_08"
down_revision = "20261122_07"
branch_labels = None
depends_on = None

PERMISSIONS = (
    "document.read", "document.create", "document.version_add",
    "document.metadata_update", "document.soft_delete",
    "document.restore", "document.purge",
)


def upgrade():
    op.drop_constraint("ck_permission_grant_permission", "permission_grants",
                       schema="accounts", type_="check")
    op.create_check_constraint(
        "ck_permission_grant_permission",
        "permission_grants",
        "permission IN ({})".format(", ".join("'{}'".format(p) for p in PERMISSIONS)),
        schema="accounts",
    )


def downgrade():
    op.drop_constraint("ck_permission_grant_permission", "permission_grants",
                       schema="accounts", type_="check")
    op.create_check_constraint(
        "ck_permission_grant_permission",
        "permission_grants",
        "permission IN ('document.read','document.create','document.version_add',"
        "'document.metadata_update','document.soft_delete')",
        schema="accounts",
    )
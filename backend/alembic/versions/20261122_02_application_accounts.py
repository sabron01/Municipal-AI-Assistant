"""Application-managed accounts and service permissions.

Revision ID: 20261122_02
Revises: 20261122_01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261122_02"
down_revision = "20261122_01"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS accounts")
    op.create_table("user_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("normalized_email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(512)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("is_central_admin", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('pending','active','disabled')", name="ck_user_accounts_status"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("normalized_email"), schema="accounts")
    op.create_table("account_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("purpose IN ('activation','password_reset')", name="ck_account_tokens_purpose"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.user_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("token_hash"), schema="accounts")
    op.create_index("ix_account_tokens_account_purpose", "account_tokens", ["account_id", "purpose"], schema="accounts")
    op.create_table("account_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.user_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("token_hash"), schema="accounts")
    op.create_index("ix_account_sessions_account_expiry", "account_sessions", ["account_id", "expires_at"], schema="accounts")
    op.create_table("permission_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission", sa.String(64), nullable=False),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("permission IN ('document.read','document.create','document.version_add','document.metadata_update','document.soft_delete')",
            name="ck_permission_grant_permission"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.user_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by"], ["accounts.user_accounts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "service_id", "permission", name="uq_permission_grant_scope"), schema="accounts")
    op.create_index("ix_permission_grants_service_permission", "permission_grants", ["service_id", "permission"], schema="accounts")
    op.create_table("account_audit",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True)),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True)),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True)),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"), schema="accounts")
    op.create_index("ix_account_audit_created", "account_audit", ["created_at"], schema="accounts")
    op.create_table("account_login_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email_hash", sa.String(64), nullable=False),
        sa.Column("ip_hash", sa.String(64), nullable=False),
        sa.Column("successful", sa.Boolean(), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"), schema="accounts")
    op.create_index("ix_account_login_email_time", "account_login_attempts", ["email_hash", "attempted_at"], schema="accounts")
    op.create_index("ix_account_login_ip_time", "account_login_attempts", ["ip_hash", "attempted_at"], schema="accounts")


def downgrade():
    op.drop_index("ix_account_login_ip_time", table_name="account_login_attempts", schema="accounts")
    op.drop_index("ix_account_login_email_time", table_name="account_login_attempts", schema="accounts")
    op.drop_table("account_login_attempts", schema="accounts")
    op.drop_index("ix_account_audit_created", table_name="account_audit", schema="accounts")
    op.drop_table("account_audit", schema="accounts")
    op.drop_index("ix_permission_grants_service_permission", table_name="permission_grants", schema="accounts")
    op.drop_table("permission_grants", schema="accounts")
    op.drop_index("ix_account_sessions_account_expiry", table_name="account_sessions", schema="accounts")
    op.drop_table("account_sessions", schema="accounts")
    op.drop_index("ix_account_tokens_account_purpose", table_name="account_tokens", schema="accounts")
    op.drop_table("account_tokens", schema="accounts")
    op.drop_table("user_accounts", schema="accounts")
    op.execute("DROP SCHEMA IF EXISTS accounts")

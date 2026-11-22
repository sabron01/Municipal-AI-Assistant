from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..documents.infrastructure.sqlalchemy_models import Base


class AccountRow(Base):
    __tablename__ = "user_accounts"
    __table_args__ = (
        CheckConstraint("status IN ('pending','active','disabled')", name="ck_user_accounts_status"),
        {"schema": "accounts"},
    )

    id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    normalized_email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    is_central_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AccountTokenRow(Base):
    __tablename__ = "account_tokens"
    __table_args__ = (
        CheckConstraint("purpose IN ('activation','password_reset')", name="ck_account_tokens_purpose"),
        Index("ix_account_tokens_account_purpose", "account_id", "purpose"),
        {"schema": "accounts"},
    )

    id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    account_id: Mapped[object] = mapped_column(UUID(as_uuid=True), ForeignKey(
        "accounts.user_accounts.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AccountSessionRow(Base):
    __tablename__ = "account_sessions"
    __table_args__ = (
        Index("ix_account_sessions_account_expiry", "account_id", "expires_at"),
        {"schema": "accounts"},
    )

    id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    account_id: Mapped[object] = mapped_column(UUID(as_uuid=True), ForeignKey(
        "accounts.user_accounts.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PermissionGrantRow(Base):
    __tablename__ = "permission_grants"
    __table_args__ = (
        UniqueConstraint("account_id", "service_id", "permission", name="uq_permission_grant_scope"),
        CheckConstraint(
            "permission IN ('document.read','document.create','document.version_add',"
            "'document.metadata_update','document.soft_delete')", name="ck_permission_grant_permission"),
        Index("ix_permission_grants_service_permission", "service_id", "permission"),
        {"schema": "accounts"},
    )

    id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    account_id: Mapped[object] = mapped_column(UUID(as_uuid=True), ForeignKey(
        "accounts.user_accounts.id", ondelete="CASCADE"), nullable=False)
    service_id: Mapped[object] = mapped_column(UUID(as_uuid=True), nullable=False)
    permission: Mapped[str] = mapped_column(String(64), nullable=False)
    granted_by: Mapped[object] = mapped_column(UUID(as_uuid=True), ForeignKey(
        "accounts.user_accounts.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AccountAuditRow(Base):
    __tablename__ = "account_audit"
    __table_args__ = (
        Index("ix_account_audit_created", "created_at"),
        {"schema": "accounts"},
    )

    id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    actor_id: Mapped[object | None] = mapped_column(UUID(as_uuid=True))
    subject_id: Mapped[object | None] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    service_id: Mapped[object | None] = mapped_column(UUID(as_uuid=True))
    outcome: Mapped[str] = mapped_column(String(16), nullable=False, default="success")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AccountLoginAttemptRow(Base):
    __tablename__ = "account_login_attempts"
    __table_args__ = (
        Index("ix_account_login_email_time", "email_hash", "attempted_at"),
        Index("ix_account_login_ip_time", "ip_hash", "attempted_at"),
        {"schema": "accounts"},
    )

    id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    ip_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    successful: Mapped[bool] = mapped_column(Boolean, nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

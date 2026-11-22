from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from sqlalchemy import delete, select, update, func
from sqlalchemy.exc import IntegrityError

from ..documents.domain.errors import AccessPolicyUnavailable
from ..documents.domain.value_objects import ServiceId
from .email import EmailDeliveryUnavailable, SmtpEmailSender
from .models import (AccountAuditRow, AccountRow, AccountSessionRow, AccountTokenRow,
                     AccountLoginAttemptRow, PermissionGrantRow)
from .security import digest_secret, hash_password, issue_secret, normalize_email, verify_password
from .settings import AccountSettings

PERMISSIONS = frozenset({
    "document.read", "document.create", "document.version_add",
    "document.metadata_update", "document.soft_delete",
})


class AccountError(Exception):
    pass


class AccountNotFound(AccountError):
    pass


class AccountConflict(AccountError):
    pass


class InvalidAccountToken(AccountError):
    pass


class AccountService:
    def __init__(self, session_factory, settings: AccountSettings, mailer: SmtpEmailSender):
        self.session_factory = session_factory
        self.settings = settings
        self.mailer = mailer

    def bootstrap_initial_admin(self) -> bool:
        email = self.settings.initial_admin_email
        if not email:
            return False
        normalized = normalize_email(email)
        with self.session_factory() as session:
            account = session.scalar(select(AccountRow).where(AccountRow.normalized_email == normalized))
            if account is not None:
                if not account.is_central_admin:
                    raise AccountConflict("Initial administrator email belongs to a non-admin account")
                if account.status == "active":
                    return False
                if account.status == "disabled":
                    raise AccountConflict("Initial administrator account is disabled")
                account.is_central_admin = True
                account.status = "pending"
            else:
                account = AccountRow(id=uuid4(), email=email.strip(), normalized_email=normalized,
                                     status="pending", is_central_admin=True)
                session.add(account)
            session.flush()
            session.add(AccountAuditRow(actor_id=None, subject_id=account.id,
                                        action="central_admin.bootstrapped"))
            token = self._issue_token(session, account, "activation")
            session.commit()
        self._send_link(email.strip(), token, "activate", "Activer votre compte administrateur")
        return True

    def create_account(self, actor_id: UUID, email: str) -> AccountRow:
        normalized = normalize_email(email)
        if not normalized or len(normalized) > 320 or "@" not in normalized:
            raise ValueError("A valid professional email address is required")
        with self.session_factory() as session:
            account = AccountRow(id=uuid4(), email=email.strip(), normalized_email=normalized, status="pending")
            session.add(account)
            try:
                session.flush()
            except IntegrityError as exc:
                session.rollback()
                raise AccountConflict("An account already exists for this email") from exc
            token = self._issue_token(session, account, "activation")
            session.add(AccountAuditRow(actor_id=actor_id, subject_id=account.id, action="account.created"))
            session.commit()
            account_id = account.id
        self._send_link(email.strip(), token, "activate", "Activer votre compte")
        return self.get_account(account_id)

    def resend_activation(self, actor_id: UUID, account_id: UUID) -> None:
        with self.session_factory() as session:
            account = session.get(AccountRow, account_id)
            if account is None or account.status != "pending":
                raise AccountNotFound("Pending account was not found")
            token = self._issue_token(session, account, "activation")
            session.add(AccountAuditRow(actor_id=actor_id, subject_id=account_id,
                                        action="account.activation_resent"))
            email = account.email
            session.commit()
        self._send_link(email, token, "activate", "Activer votre compte")

    def activate(self, token: str, password: str) -> None:
        password_hash = hash_password(password)
        self._consume_token(token, "activation", password_hash=password_hash)

    def request_password_reset(self, actor_id: UUID, account_id: UUID) -> None:
        with self.session_factory() as session:
            account = session.get(AccountRow, account_id)
            if account is None or account.status != "active":
                raise AccountNotFound("Active account was not found")
            token = self._issue_token(session, account, "password_reset")
            session.add(AccountAuditRow(actor_id=actor_id, subject_id=account_id,
                                        action="account.password_reset_requested"))
            email = account.email
            session.commit()
        self._send_link(email, token, "reset-password", "Réinitialiser votre mot de passe")

    def reset_password(self, token: str, password: str) -> None:
        password_hash = hash_password(password)
        self._consume_token(token, "password_reset", password_hash=password_hash)

    def _consume_token(self, token: str, purpose: str, *, password_hash: str) -> None:
        now = datetime.now(timezone.utc)
        with self.session_factory() as session:
            record = session.scalar(select(AccountTokenRow).where(
                AccountTokenRow.token_hash == digest_secret(token),
                AccountTokenRow.purpose == purpose,
                AccountTokenRow.consumed_at.is_(None),
                AccountTokenRow.expires_at > now,
            ).with_for_update())
            if record is None:
                raise InvalidAccountToken("The link is invalid or expired")
            account = session.scalar(select(AccountRow).where(AccountRow.id == record.account_id).with_for_update())
            if account is None:
                raise InvalidAccountToken("The link is invalid or expired")
            if purpose == "activation" and account.status != "pending":
                raise InvalidAccountToken("The link is invalid or expired")
            if purpose == "password_reset" and account.status != "active":
                raise InvalidAccountToken("The link is invalid or expired")
            record.consumed_at = now
            account.password_hash = password_hash
            account.status = "active"
            account.updated_at = now
            session.execute(update(AccountSessionRow).where(
                AccountSessionRow.account_id == account.id,
                AccountSessionRow.revoked_at.is_(None),
            ).values(revoked_at=now))
            session.add(AccountAuditRow(actor_id=account.id, subject_id=account.id,
                                        action=f"account.{purpose}_completed"))
            session.commit()

    def authenticate(self, email: str, password: str, source_ip: str) -> tuple[AccountRow, str, str] | None:
        normalized = normalize_email(email)
        now = datetime.now(timezone.utc)
        email_key, ip_key = digest_secret(normalized), digest_secret(source_ip or "unknown")
        with self.session_factory() as session:
            window_start = now - timedelta(minutes=15)
            email_failures = session.scalar(select(func.count()).select_from(AccountLoginAttemptRow).where(
                AccountLoginAttemptRow.email_hash == email_key,
                AccountLoginAttemptRow.successful.is_(False),
                AccountLoginAttemptRow.attempted_at >= window_start)) or 0
            ip_failures = session.scalar(select(func.count()).select_from(AccountLoginAttemptRow).where(
                AccountLoginAttemptRow.ip_hash == ip_key,
                AccountLoginAttemptRow.successful.is_(False),
                AccountLoginAttemptRow.attempted_at >= window_start)) or 0
            throttled = email_failures >= 10 or ip_failures >= 100
            account = session.scalar(select(AccountRow).where(AccountRow.normalized_email == normalized))
            hash_value = account.password_hash if account is not None else _DUMMY_HASH
            verified = verify_password(hash_value, password)
            valid = not throttled and verified and account is not None and account.status == "active"
            session.add(AccountLoginAttemptRow(email_hash=email_key, ip_hash=ip_key,
                                               successful=bool(valid)))
            session.execute(delete(AccountLoginAttemptRow).where(
                AccountLoginAttemptRow.attempted_at < now - timedelta(days=1)))
            if not valid:
                session.add(AccountAuditRow(actor_id=account.id if account else None,
                    subject_id=account.id if account else None,
                    action="auth.login_denied", outcome="denied"))
                session.commit()
                return None
            session_token, csrf_token = issue_secret(), issue_secret()
            session.add(AccountSessionRow(account_id=account.id,
                token_hash=digest_secret(session_token), csrf_hash=digest_secret(csrf_token),
                expires_at=now + timedelta(hours=max(1, self.settings.session_ttl_hours))))
            session.add(AccountAuditRow(actor_id=account.id, subject_id=account.id, action="auth.login"))
            session.commit()
            return account, session_token, csrf_token

    def current_session(self, raw_token: str | None) -> tuple[AccountRow, AccountSessionRow] | None:
        if not raw_token:
            return None
        now = datetime.now(timezone.utc)
        with self.session_factory() as session:
            pair = session.execute(select(AccountRow, AccountSessionRow).join(
                AccountSessionRow, AccountSessionRow.account_id == AccountRow.id).where(
                AccountSessionRow.token_hash == digest_secret(raw_token),
                AccountSessionRow.revoked_at.is_(None), AccountSessionRow.expires_at > now,
                AccountRow.status == "active",
            )).first()
            return pair if pair else None

    def logout(self, raw_token: str) -> None:
        with self.session_factory() as session:
            record = session.scalar(select(AccountSessionRow).where(
                AccountSessionRow.token_hash == digest_secret(raw_token),
                AccountSessionRow.revoked_at.is_(None)))
            if record is not None:
                record.revoked_at = datetime.now(timezone.utc)
                session.add(AccountAuditRow(actor_id=record.account_id, subject_id=record.account_id,
                                            action="auth.logout"))
                session.commit()

    def get_account(self, account_id: UUID) -> AccountRow:
        with self.session_factory() as session:
            account = session.get(AccountRow, account_id)
            if account is None:
                raise AccountNotFound("Account was not found")
            return account

    def list_accounts(self) -> list[AccountRow]:
        with self.session_factory() as session:
            return list(session.scalars(select(AccountRow).order_by(AccountRow.email)))

    def set_account_status(self, actor_id: UUID, account_id: UUID, status: str) -> AccountRow:
        if status not in {"active", "disabled"}:
            raise ValueError("Unsupported account status")
        with self.session_factory() as session:
            account = session.scalar(select(AccountRow).where(AccountRow.id == account_id).with_for_update())
            if account is None:
                raise AccountNotFound("Account was not found")
            if status == "active" and account.status != "disabled":
                raise AccountConflict("Only a disabled account can be reactivated")
            if status == "active" and not account.password_hash:
                raise AccountConflict("A disabled account without a password must be activated again")
            if status == "disabled" and account.is_central_admin and account.status == "active":
                admins = session.scalar(select(func.count()).select_from(AccountRow).where(
                    AccountRow.is_central_admin.is_(True), AccountRow.status == "active")) or 0
                if admins <= 1:
                    raise AccountConflict("The last active central administrator cannot be disabled")
            account.status = status
            account.updated_at = datetime.now(timezone.utc)
            if status == "disabled":
                session.execute(update(AccountSessionRow).where(
                    AccountSessionRow.account_id == account_id,
                    AccountSessionRow.revoked_at.is_(None),
                ).values(revoked_at=account.updated_at))
            session.add(AccountAuditRow(actor_id=actor_id, subject_id=account_id,
                                        action=f"account.{status}"))
            session.commit()
            return account

    def set_central_admin(self, actor_id: UUID, account_id: UUID, enabled: bool) -> AccountRow:
        with self.session_factory() as session:
            account = session.scalar(select(AccountRow).where(AccountRow.id == account_id).with_for_update())
            if account is None:
                raise AccountNotFound("Account was not found")
            if not enabled and account.is_central_admin and account.status == "active":
                admins = session.scalar(select(func.count()).select_from(AccountRow).where(
                    AccountRow.is_central_admin.is_(True), AccountRow.status == "active")) or 0
                if admins <= 1:
                    raise AccountConflict("The last active central administrator cannot be removed")
            account.is_central_admin = enabled
            account.updated_at = datetime.now(timezone.utc)
            session.add(AccountAuditRow(actor_id=actor_id, subject_id=account_id,
                                        action="account.central_admin_enabled" if enabled
                                        else "account.central_admin_disabled"))
            session.commit()
            return account

    def replace_permissions(self, actor_id: UUID, account_id: UUID, service_id: UUID,
                           permissions: set[str]) -> None:
        if not permissions.issubset(PERMISSIONS):
            raise ValueError("Unsupported document permission")
        with self.session_factory() as session:
            account = session.get(AccountRow, account_id)
            if account is None:
                raise AccountNotFound("Account was not found")
            session.execute(delete(PermissionGrantRow).where(
                PermissionGrantRow.account_id == account_id,
                PermissionGrantRow.service_id == service_id))
            for permission in sorted(permissions):
                session.add(PermissionGrantRow(account_id=account_id, service_id=service_id,
                    permission=permission, granted_by=actor_id))
            session.add(AccountAuditRow(actor_id=actor_id, subject_id=account_id,
                service_id=service_id, action="permission.scope_replaced"))
            session.commit()

    def _issue_token(self, session, account: AccountRow, purpose: str) -> str:
        now = datetime.now(timezone.utc)
        session.execute(update(AccountTokenRow).where(
            AccountTokenRow.account_id == account.id,
            AccountTokenRow.purpose == purpose,
            AccountTokenRow.consumed_at.is_(None),
        ).values(consumed_at=now))
        token = issue_secret()
        days = self.settings.activation_ttl_days if purpose == "activation" else self.settings.password_reset_ttl_days
        session.add(AccountTokenRow(account_id=account.id, token_hash=digest_secret(token),
            purpose=purpose, expires_at=now + timedelta(days=days)))
        return token

    def _send_link(self, email: str, token: str, path: str, subject: str) -> None:
        base_url = self.settings.public_base_url
        if not base_url:
            raise EmailDeliveryUnavailable("APP_PUBLIC_BASE_URL is not configured")
        parsed_url = urlsplit(base_url)
        local_http_hosts = {"127.0.0.1", "localhost", "::1"}
        if (parsed_url.scheme != "https" and not
                (parsed_url.scheme == "http" and parsed_url.hostname in local_http_hosts)):
            raise EmailDeliveryUnavailable("APP_PUBLIC_BASE_URL must use HTTPS outside localhost")
        if not parsed_url.netloc or parsed_url.query or parsed_url.fragment or parsed_url.username or parsed_url.password:
            raise EmailDeliveryUnavailable("APP_PUBLIC_BASE_URL is invalid")
        url = f"{base_url.rstrip('/')}/api/v1/auth/{path}?token={token}"
        ttl_days = self.settings.password_reset_ttl_days if path == "reset-password" else self.settings.activation_ttl_days
        self.mailer.send(recipient=email, subject=subject,
            body=f"Ouvrez ce lien à usage unique dans les {ttl_days} jours :\n\n{url}\n")


class DatabaseDocumentAccessPolicy:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def require(self, actor_id: UUID, action: str, service_id: ServiceId) -> None:
        if action == "document.list":
            action = "document.read"
        if action not in PERMISSIONS:
            raise AccessPolicyUnavailable("Unknown document permission")
        with self.session_factory() as session:
            allowed = session.scalar(select(AccountRow.id).join(
                PermissionGrantRow, PermissionGrantRow.account_id == AccountRow.id).where(
                AccountRow.id == actor_id, AccountRow.status == "active",
                PermissionGrantRow.service_id == service_id.value,
                PermissionGrantRow.permission == action,
            ).limit(1))
            if allowed is None:
                from ..documents.domain.errors import DocumentNotFound
                raise DocumentNotFound("Document was not found")

    def is_central_admin(self, actor_id: UUID) -> bool:
        with self.session_factory() as session:
            return bool(session.scalar(select(AccountRow.id).where(
                AccountRow.id == actor_id, AccountRow.status == "active",
                AccountRow.is_central_admin.is_(True)).limit(1)))

    def permissions_for(self, account_id: UUID, service_id: UUID) -> list[str]:
        with self.session_factory() as session:
            return list(session.scalars(select(PermissionGrantRow.permission).where(
                PermissionGrantRow.account_id == account_id,
                PermissionGrantRow.service_id == service_id).order_by(PermissionGrantRow.permission)))

    def permissions_by_service(self, account_id: UUID) -> dict[str, list[str]]:
        with self.session_factory() as session:
            rows = session.execute(select(PermissionGrantRow.service_id,
                PermissionGrantRow.permission).where(PermissionGrantRow.account_id == account_id)
                .order_by(PermissionGrantRow.service_id, PermissionGrantRow.permission)).all()
            result: dict[str, list[str]] = {}
            for service_id, permission in rows:
                result.setdefault(str(service_id), []).append(permission)
            return result


_DUMMY_HASH = hash_password("Unrelated dummy password used for timing equalization")

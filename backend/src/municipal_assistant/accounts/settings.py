import os
from pathlib import Path
from dataclasses import dataclass

from dotenv import load_dotenv

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
load_dotenv(REPOSITORY_ROOT / ".env", override=False)


def _boolean(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class AccountSettings:
    database_url: str | None
    initial_admin_email: str | None
    public_base_url: str | None
    smtp_host: str | None
    smtp_port: int
    smtp_username: str | None
    smtp_password: str | None
    smtp_sender: str | None
    smtp_starttls: bool
    smtp_use_ssl: bool
    session_ttl_hours: int
    cookie_secure: bool
    auth_enabled: bool
    activation_ttl_days: int
    password_reset_ttl_days: int
    login_identifier: str
    mfa_required: bool

    @property
    def session_cookie_name(self) -> str:
        return "__Host-maa_session" if self.cookie_secure else "maa_session"

    @property
    def csrf_cookie_name(self) -> str:
        return "__Host-maa_csrf" if self.cookie_secure else "maa_csrf"

    @classmethod
    def from_environment(cls) -> "AccountSettings":
        return cls(
            database_url=os.getenv("DATABASE_URL"),
            initial_admin_email=os.getenv("INITIAL_CENTRAL_ADMIN_EMAIL") or None,
            public_base_url=os.getenv("APP_PUBLIC_BASE_URL") or None,
            smtp_host=os.getenv("SMTP_HOST") or None,
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_username=os.getenv("SMTP_USERNAME") or None,
            smtp_password=os.getenv("SMTP_PASSWORD") or None,
            smtp_sender=os.getenv("SMTP_SENDER") or None,
            smtp_starttls=_boolean("SMTP_STARTTLS", True),
            smtp_use_ssl=_boolean("SMTP_USE_SSL", False),
            session_ttl_hours=int(os.getenv("AUTH_SESSION_TTL_HOURS", "8")),
            cookie_secure=_boolean("AUTH_COOKIE_SECURE", True),
            auth_enabled=_boolean("AUTH_ENABLED", False),
            activation_ttl_days=max(1, int(os.getenv("ACCOUNT_ACTIVATION_LINK_TTL_DAYS", "7"))),
            password_reset_ttl_days=max(1, int(os.getenv("ACCOUNT_PASSWORD_RESET_LINK_TTL_DAYS", "7"))),
            login_identifier=os.getenv("AUTH_LOGIN_IDENTIFIER", "email").strip().lower(),
            mfa_required=_boolean("AUTH_MFA_REQUIRED", False),
        )

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .email import SmtpEmailSender
from .service import AccountService
from .settings import AccountSettings


def build_account_service(settings: AccountSettings):
    if settings.login_identifier != "email":
        raise ValueError("AUTH_LOGIN_IDENTIFIER must be email")
    if settings.auth_enabled and settings.mfa_required:
        raise ValueError("MFA is not implemented in v1; keep AUTH_MFA_REQUIRED=false")
    if not settings.database_url:
        return None, None
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    return AccountService(sessions, settings, SmtpEmailSender(settings)), engine

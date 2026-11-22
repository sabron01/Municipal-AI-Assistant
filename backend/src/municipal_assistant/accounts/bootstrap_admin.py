"""One-time command: python -m municipal_assistant.accounts.bootstrap_admin"""
from .composition import build_account_service
from .settings import AccountSettings


def main() -> int:
    settings = AccountSettings.from_environment()
    if not settings.initial_admin_email:
        raise SystemExit("INITIAL_CENTRAL_ADMIN_EMAIL is required")
    if not settings.smtp_host or not settings.smtp_sender or not settings.public_base_url:
        raise SystemExit("SMTP_HOST, SMTP_SENDER and APP_PUBLIC_BASE_URL must be configured")
    service, engine = build_account_service(settings)
    if service is None:
        raise SystemExit("DATABASE_URL is required")
    try:
        created = service.bootstrap_initial_admin()
        print("Activation email sent." if created else "Initial administrator already active.")
        print("Remove INITIAL_CENTRAL_ADMIN_EMAIL from the environment after bootstrap.")
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

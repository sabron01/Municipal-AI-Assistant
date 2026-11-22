from email.message import EmailMessage
import smtplib
import ssl

from .settings import AccountSettings


class EmailDeliveryUnavailable(RuntimeError):
    pass


class SmtpEmailSender:
    def __init__(self, settings: AccountSettings):
        self.settings = settings

    def send(self, *, recipient: str, subject: str, body: str) -> None:
        settings = self.settings
        if not all((settings.smtp_host, settings.smtp_sender, settings.public_base_url)):
            raise EmailDeliveryUnavailable("Professional email delivery is not configured")
        if settings.smtp_starttls and settings.smtp_use_ssl:
            raise EmailDeliveryUnavailable("Choose SMTP STARTTLS or SMTP SSL, not both")
        if not settings.smtp_starttls and not settings.smtp_use_ssl:
            raise EmailDeliveryUnavailable("SMTP must use STARTTLS or SSL")
        message = EmailMessage()
        message["From"] = settings.smtp_sender
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        try:
            if settings.smtp_use_ssl:
                client_context = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port,
                    timeout=10, context=ssl.create_default_context())
            else:
                client_context = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
            with client_context as client:
                if settings.smtp_starttls:
                    client.ehlo()
                    client.starttls(context=ssl.create_default_context())
                    client.ehlo()
                if settings.smtp_username:
                    client.login(settings.smtp_username, settings.smtp_password or "")
                client.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            raise EmailDeliveryUnavailable("Professional email delivery failed") from exc

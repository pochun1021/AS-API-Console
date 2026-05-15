from __future__ import annotations

try:
    from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
except ModuleNotFoundError:  # pragma: no cover - dependency guard for environments not yet synced
    ConnectionConfig = FastMail = MessageSchema = MessageType = None  # type: ignore[assignment]

from app.core.config import get_settings


class MailService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def is_enabled(self) -> bool:
        required = [
            self.settings.mail_server,
            self.settings.mail_from,
        ]
        return bool(self.settings.mail_enabled and all(required))

    def _mail_credentials(self) -> tuple[str, str, bool]:
        username = (self.settings.mail_username or "").strip()
        password = (self.settings.mail_password or "").strip()
        use_credentials = bool(username and password)
        return username, password, use_credentials

    async def send_key_issued_notification(
        self,
        *,
        to_email: str,
        owner_name: str,
        application_id: str,
        app_domain: str,
    ) -> None:
        if not self.is_enabled():
            return
        if ConnectionConfig is None:
            raise RuntimeError("fastapi-mail is not installed")
        username, password, use_credentials = self._mail_credentials()

        conf = ConnectionConfig(
            MAIL_USERNAME=username,
            MAIL_PASSWORD=password,
            MAIL_FROM=self.settings.mail_from,
            MAIL_FROM_NAME=self.settings.mail_from_name,
            MAIL_PORT=self.settings.mail_port,
            MAIL_SERVER=self.settings.mail_server,
            MAIL_STARTTLS=self.settings.mail_starttls,
            MAIL_SSL_TLS=self.settings.mail_ssl_tls,
            USE_CREDENTIALS=use_credentials,
            VALIDATE_CERTS=self.settings.mail_validate_certs,
        )
        message = MessageSchema(
            subject="[AS API Console] Your API key has been issued",
            recipients=[to_email],
            body=(
                f"<p>Hello {owner_name},</p>"
                "<p>Your pending API key application has been issued.</p>"
                f"<p>Application ID: <b>{application_id}</b></p>"
                f"<p>Please sign in to <a href=\"{app_domain}\">AS API Console</a> to review your key details.</p>"
                "<p>This notification does not contain plaintext API key content.</p>"
            ),
            subtype=MessageType.html,
        )

        fm = FastMail(conf)
        await fm.send_message(message)

from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr

try:
    import aiosmtplib
except ModuleNotFoundError:  # pragma: no cover - dependency guard for environments not yet synced
    aiosmtplib = None  # type: ignore[assignment]


@dataclass(frozen=True)
class SMTPDeliveryConfig:
    host: str
    port: int
    from_email: str
    from_name: str
    username: str = ""
    password: str = ""
    starttls: bool = True
    ssl_tls: bool = False
    validate_certs: bool = True

    @property
    def use_credentials(self) -> bool:
        return bool(self.username and self.password)


async def send_html_message(
    config: SMTPDeliveryConfig,
    *,
    subject: str,
    recipients: list[str],
    body: str,
) -> None:
    if aiosmtplib is None:
        raise RuntimeError("aiosmtplib is not installed")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((config.from_name, config.from_email))
    message["To"] = ", ".join(recipients)
    message.set_content("HTML email content is attached as an alternative body.")
    message.add_alternative(body, subtype="html")

    await aiosmtplib.send(
        message,
        hostname=config.host,
        port=config.port,
        username=config.username if config.use_credentials else None,
        password=config.password if config.use_credentials else None,
        start_tls=config.starttls and not config.ssl_tls,
        use_tls=config.ssl_tls,
        validate_certs=config.validate_certs,
    )

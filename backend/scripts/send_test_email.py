from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from app.services.smtp_delivery import SMTPDeliveryConfig, send_html_message

DEFAULT_MAIL_FROM = "noreply@as.edu.tw"


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


async def send_test_email(to_email: str) -> None:
    enabled = as_bool(os.getenv("MAIL_ENABLED"), False)
    if not enabled:
        raise RuntimeError("MAIL_ENABLED is false; please set MAIL_ENABLED=true in .env")

    mail_server = os.getenv("MAIL_SERVER", "").strip()
    mail_username = os.getenv("MAIL_USERNAME", "").strip()
    mail_password = os.getenv("MAIL_PASSWORD", "").strip()

    if not mail_server:
        raise RuntimeError("MAIL_SERVER is empty")

    use_credentials = bool(mail_username and mail_password)

    config = SMTPDeliveryConfig(
        host=mail_server,
        port=int(os.getenv("MAIL_PORT", "587")),
        from_email=DEFAULT_MAIL_FROM,
        from_name=os.getenv("MAIL_FROM_NAME", "AS API Console"),
        username=mail_username if use_credentials else "",
        password=mail_password if use_credentials else "",
        starttls=as_bool(os.getenv("MAIL_STARTTLS"), True),
        ssl_tls=as_bool(os.getenv("MAIL_SSL_TLS"), False),
        validate_certs=as_bool(os.getenv("MAIL_VALIDATE_CERTS"), True),
    )
    await send_html_message(
        config,
        subject="[AS API Console] SMTP test",
        recipients=[to_email],
        body=(
            "<p>This is a test email from AS API Console.</p>"
            "<p>If you received this, SMTP settings are working.</p>"
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Send SMTP test email using .env MAIL_* settings")
    parser.add_argument("--to", required=True, help="Recipient email address")
    parser.add_argument("--env-file", default=".env", help="Path to env file (default: .env)")
    args = parser.parse_args()

    load_env_file(Path(args.env_file))
    asyncio.run(send_test_email(args.to))
    print(f"OK: test email sent to {args.to}")


if __name__ == "__main__":
    main()

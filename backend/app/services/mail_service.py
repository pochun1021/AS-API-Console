from __future__ import annotations

import logging
from asyncio import run as run_async
from datetime import UTC, datetime
from threading import Thread
from typing import Callable
from zoneinfo import ZoneInfo

try:
    from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
except ModuleNotFoundError:  # pragma: no cover - dependency guard for environments not yet synced
    ConnectionConfig = FastMail = MessageSchema = MessageType = None  # type: ignore[assignment]

from app.core.config import get_settings

MAIL_DISPLAY_TZ = ZoneInfo("Asia/Taipei")


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

    def dispatch_background(self, task_factory: Callable[[], object], *, error_message: str) -> None:
        def _runner() -> None:
            try:
                run_async(task_factory())
            except Exception:  # noqa: BLE001
                logging.exception(error_message)

        try:
            Thread(target=_runner, name="mail-dispatch", daemon=True).start()
        except Exception:  # noqa: BLE001
            logging.exception(error_message)

    async def _send_html(self, *, subject: str, recipients: list[str], body: str) -> None:
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
            subject=subject,
            recipients=recipients,
            body=body,
            subtype=MessageType.html,
        )
        fm = FastMail(conf)
        await fm.send_message(message)

    async def send_key_expiration_notice(
        self,
        *,
        to_email: str,
        owner_name: str,
        days_before: int,
        expires_at: datetime,
        app_domain: str,
    ) -> None:
        expires_at_utc = expires_at if expires_at.tzinfo is not None else expires_at.replace(tzinfo=UTC)
        expires_at_taipei = expires_at_utc.astimezone(MAIL_DISPLAY_TZ)
        expires_text_zh = expires_at_taipei.strftime("%Y-%m-%d %H:%M 台灣時間")
        expires_text_en = expires_at_taipei.strftime("%Y-%m-%d %H:%M Asia/Taipei")
        await self._send_html(
            subject=f"[AS API Console] API Key 將於 {days_before} 天後到期 / Expires in {days_before} days",
            recipients=[to_email],
            body=(
                "<p>親愛的使用者，您好：</p>"
                f"<p>提醒您，您的 API Key 將於 {days_before} 天後到期。</p>"
                f"<p>到期時間：{expires_text_zh}</p>"
                "<p>您可於到期前或到期後進行展延（extend）。</p>"
                "<p>若此操作非您本人執行，請立即連繫資訊服務處。</p>"
                "<p>若您有任何疑問，歡迎向資訊服務處服務台反映。</p>"
                "<p>聯絡窗口：中央研究院資訊服務處<br/>"
                "線上服務台（上班時間）：https://its.sinica.edu.tw/online（密碼27898855）<br/>"
                "電話（上班時間）：02-27898855<br/>"
                "信箱：its@sinica.edu.tw</p>"
                "<p>中央研究院資訊服務處 敬啟</p>"
                "<hr/>"
                "<p>Dear user,</p>"
                f"<p>This is a reminder that your API key will expire in {days_before} days.</p>"
                f"<p>Expiration time: {expires_text_en}</p>"
                "<p>You can extend this key before or after expiration.</p>"
                "<p>If this action was not performed by you, please contact the IT Service Desk immediately.</p>"
                "<p>If you have any questions, please contact the IT Service Desk.</p>"
                "<p>Contact: Institute of Information Science, Academia Sinica IT Service Desk<br/>"
                "Online Service Desk (business hours): https://its.sinica.edu.tw/online (password: 27898855)<br/>"
                "Phone (business hours): 02-27898855<br/>"
                "Email: its@sinica.edu.tw</p>"
                "<p>Sincerely,<br/>Academia Sinica IT Service Desk</p>"
            ),
        )

from __future__ import annotations

import calendar
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
MAIL_FROM_ADDRESS = "noreply@as.edu.tw"


class MailService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def is_enabled(self) -> bool:
        required = [
            self.settings.mail_server,
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
            MAIL_FROM=MAIL_FROM_ADDRESS,
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
        expires_text_zh = (
            f"{expires_at_taipei.year} 年 {expires_at_taipei.month} 月 "
            f"{expires_at_taipei.day} 日 {expires_at_taipei.strftime('%H:%M')}（UTC+8）"
        )
        expires_text_en = (
            f"{calendar.month_name[expires_at_taipei.month]} {expires_at_taipei.day}, "
            f"{expires_at_taipei.year}, {expires_at_taipei.strftime('%H:%M')} (UTC+8)"
        )
        await self._send_html(
            subject=(
                f"[AS-ITS] API Key 將於 {days_before} 天後到期 / "
                f"API Key Expiration Notice ({days_before} Days Remaining)"
            ),
            recipients=[to_email],
            body=(
                "<p>親愛的使用者，您好：</p>"
                f"<p>提醒您，您的 API Key 將於 {days_before} 天後到期。</p>"
                f"<p>到期時間：{expires_text_zh}</p>"
                "<p>如需持續使用，請於到期前或到期後至系統進行展延（Extend）作業。</p>"
                "<p>服務申請／展延網址：https://api.ascs.sinica.edu.tw/main/</p>"
                "<p>若您未曾申請或使用此 API Key，請與資訊服務處服務台聯繫。</p>"
                "<p>如有其他相關問題，歡迎與我們聯絡。</p>"
                "<p>聯絡資訊：<br/>"
                "線上服務台（上班時間）：https://its.sinica.edu.tw/online<br/>"
                "電話（上班時間）：(02) 2789-8855<br/>"
                "電子郵件：its@sinica.edu.tw</p>"
                "<p>中央研究院資訊服務處 敬啟</p>"
                "<hr/>"
                "<p>Dear User,</p>"
                f"<p>This is a reminder that your API Key will expire in {days_before} days.</p>"
                f"<p>Expiration Date and Time: {expires_text_en}</p>"
                "<p>If you wish to continue using this API Key, please extend it through the system "
                "either before or after its expiration.</p>"
                "<p>Application / Extension URL: https://api.ascs.sinica.edu.tw/main/</p>"
                "<p>If you did not apply for or use this API Key, please contact the IT Service Desk.</p>"
                "<p>For any questions, please feel free to contact us.</p>"
                "<p>Contact Information:<br/>"
                "Online Service Desk (Business Hours): https://its.sinica.edu.tw/online<br/>"
                "Phone (Business Hours): +886-2-2789-8855<br/>"
                "Email: its@sinica.edu.tw</p>"
                "<p>Sincerely,</p>"
                "<p>The Department of Information Technology Services<br/>Academia Sinica</p>"
            ),
        )

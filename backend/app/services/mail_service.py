from __future__ import annotations

import logging
from asyncio import run as run_async
from datetime import UTC, datetime
from threading import Thread
from typing import Callable

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

    async def send_key_renewed_notification(
        self,
        *,
        to_email: str,
        owner_name: str,
        app_domain: str,
    ) -> None:
        await self._send_html(
            subject="[AS API Console] API Key 已更新 / API key renew",
            recipients=[to_email],
            body=(
                "<p>親愛的使用者，您好：</p>"
                "<p>您已成功更新 API Key 請妥善保管</p>"
                "<p>若此操作非您本人執行，請立即連繫資訊服務處。</p>"
                "<p>若您有任何疑問，歡迎向資訊服務處服務台反映。</p>"
                "<p>聯絡窗口：中央研究院資訊服務處<br/>"
                "線上服務台（上班時間）：https://its.sinica.edu.tw/online（密碼27898855）<br/>"
                "電話（上班時間）：02-27898855<br/>"
                "信箱：its@sinica.edu.tw</p>"
                "<p>中央研究院資訊服務處 敬啟</p>"
                "<hr/>"
                f"<p>Dear user,</p>"
                "<p>You have successfully renewed your API key. Please keep it secure.</p>"
                "<p>If this action was not performed by you, please contact the IT Service Desk immediately.</p>"
                "<p>If you have any questions, please contact the IT Service Desk.</p>"
                "<p>Contact: Institute of Information Science, Academia Sinica IT Service Desk<br/>"
                "Online Service Desk (business hours): https://its.sinica.edu.tw/online (password: 27898855)<br/>"
                "Phone (business hours): 02-27898855<br/>"
                "Email: its@sinica.edu.tw</p>"
                "<p>Sincerely,<br/>Academia Sinica IT Service Desk</p>"
            ),
        )

    async def send_application_received_to_applicant(
        self,
        *,
        to_email: str,
        owner_name: str,
        application_id: str,
        app_domain: str,
    ) -> None:
        await self._send_html(
            subject="[AS API Console] 成功申請 API Key / API key application successful",
            recipients=[to_email],
            body=(
                "<p>親愛的使用者，您好：</p>"
                "<p>感謝您申請 API Key 請妥善保管</p>"
                "<p>若此操作非您本人執行，請立即連繫資訊服務處。</p>"
                "<p>若您有任何疑問，歡迎向資訊服務處服務台反映。</p>"
                "<p>聯絡窗口：中央研究院資訊服務處<br/>"
                "線上服務台（上班時間）：https://its.sinica.edu.tw/online（密碼27898855）<br/>"
                "電話（上班時間）：02-27898855<br/>"
                "信箱：its@sinica.edu.tw</p>"
                "<p>中央研究院資訊服務處 敬啟</p>"
                "<hr/>"
                "<p>Dear user,</p>"
                "<p>Thank you for applying for an API key. Please keep it secure.</p>"
                "<p>If this action was not performed by you, please contact the IT Service Desk immediately.</p>"
                "<p>If you have any questions, please contact the IT Service Desk.</p>"
                "<p>Contact: Institute of Information Science, Academia Sinica IT Service Desk<br/>"
                "Online Service Desk (business hours): https://its.sinica.edu.tw/online (password: 27898855)<br/>"
                "Phone (business hours): 02-27898855<br/>"
                "Email: its@sinica.edu.tw</p>"
                "<p>Sincerely,<br/>Academia Sinica IT Service Desk</p>"
            ),
        )

    async def send_provider_issuance_failed_to_admins(
        self,
        *,
        to_emails: list[str],
        operation: str,
        actor_account: str,
        actor_role: str,
        target_account: str,
        error_code: str,
    ) -> None:
        if not to_emails:
            return
        await self._send_html(
            subject="[AS API Console] API Key 配發失敗通知 / API key issuance failure",
            recipients=to_emails,
            body=(
                "<p>管理者您好：</p>"
                "<p>系統偵測到 API Key 配發失敗，請協助確認 provider 連線與服務狀態。</p>"
                f"<p>操作類型：{operation}<br/>"
                f"操作者：{actor_account}（{actor_role}）<br/>"
                f"目標帳號：{target_account}<br/>"
                f"錯誤代碼：{error_code}</p>"
                "<p>此通知不包含任何明文金鑰或敏感憑證。</p>"
                "<hr/>"
                "<p>Dear admin,</p>"
                "<p>The system detected an API key issuance failure. Please verify provider connectivity and service status.</p>"
                f"<p>Operation: {operation}<br/>"
                f"Actor: {actor_account} ({actor_role})<br/>"
                f"Target account: {target_account}<br/>"
                f"Error code: {error_code}</p>"
                "<p>This notice does not include plaintext keys or sensitive credentials.</p>"
            ),
        )

    async def send_key_expiration_notice(
        self,
        *,
        to_email: str,
        owner_name: str,
        expires_at: datetime,
        app_domain: str,
    ) -> None:
        expires_at_utc = expires_at if expires_at.tzinfo is not None else expires_at.replace(tzinfo=UTC)
        expires_text = expires_at_utc.strftime("%Y-%m-%d %H:%M UTC")
        await self._send_html(
            subject="[AS API Console] API Key 即將到期提醒 / API key expiration reminder",
            recipients=[to_email],
            body=(
                "<p>親愛的使用者，您好：</p>"
                "<p>提醒您，您的 API Key 將於下列時間到期：</p>"
                f"<p>到期時間：{expires_text}</p>"
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
                "<p>This is a reminder that your API key will expire at:</p>"
                f"<p>Expiration time: {expires_text}</p>"
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

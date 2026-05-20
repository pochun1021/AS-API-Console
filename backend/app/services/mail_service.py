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

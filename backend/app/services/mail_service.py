from __future__ import annotations

from typing import Iterable

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

    async def send_key_issued_notification(
        self,
        *,
        to_email: str,
        owner_name: str,
        application_id: str,
        app_domain: str,
    ) -> None:
        await self._send_html(
            subject="[AS API Console] Your API key has been issued",
            recipients=[to_email],
            body=(
                f"<p>Hello {owner_name},</p>"
                "<p>Your pending API key application has been issued.</p>"
                f"<p>Application ID: <b>{application_id}</b></p>"
                f"<p>Please sign in to <a href=\"{app_domain}\">AS API Console</a> to review your key details.</p>"
                "<p>This notification does not contain plaintext API key content.</p>"
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
            subject="[AS API Console] 已收到您的申請 / We received your application",
            recipients=[to_email],
            body=(
                f"<p>{owner_name} 您好：</p>"
                "<p>我們已收到您的 API Key 申請，管理者將審理後配發金鑰，請耐心等候。</p>"
                f"<p>您可登入 <a href=\"{app_domain}\">AS API Console</a> 查看最新狀態。</p>"
                "<hr/>"
                f"<p>Hello {owner_name},</p>"
                "<p>We have received your API key application. Please wait while admins review and issue the key.</p>"
                f"<p>You can sign in to <a href=\"{app_domain}\">AS API Console</a> to check the latest status.</p>"
            ),
        )

    async def send_application_received_to_admins(
        self,
        *,
        recipients: Iterable[str],
        application_id: str,
        applicant_account: str,
        applicant_name: str,
        applicant_email: str,
        applicant_department: str,
        application_date: str,
        duration_months: int,
        purpose: str,
        app_domain: str,
    ) -> None:
        to_list = [r for r in dict.fromkeys(recipients) if r]
        if not to_list:
            return

        await self._send_html(
            subject="[AS API Console] 新申請待審 / New application pending review",
            recipients=to_list,
            body=(
                "<p>管理者您好：</p>"
                "<p>有新的 API Key 申請待審，請前往後台審理與配發。</p>"
                f"<p>申請單號：<b>{application_id}</b></p>"
                f"<p>申請者：{applicant_account} / {applicant_name} / {applicant_email} / {applicant_department}</p>"
                f"<p>申請日期：{application_date}；時長：{duration_months} 個月</p>"
                f"<p>用途：{purpose}</p>"
                f"<p><a href=\"{app_domain}\">前往 AS API Console</a></p>"
                "<hr/>"
                "<p>Hello Admin,</p>"
                "<p>A new API key application is pending review. Please review and issue it in the console.</p>"
                f"<p>Application ID: <b>{application_id}</b></p>"
                f"<p>Applicant: {applicant_account} / {applicant_name} / {applicant_email} / {applicant_department}</p>"
                f"<p>Application date: {application_date}; Duration: {duration_months} month(s)</p>"
                f"<p>Purpose: {purpose}</p>"
                f"<p><a href=\"{app_domain}\">Open AS API Console</a></p>"
            ),
        )

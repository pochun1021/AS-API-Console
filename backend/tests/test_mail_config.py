from __future__ import annotations

from asyncio import run as run_async


def test_mail_service_uses_hardcoded_mail_from(monkeypatch):
    from app.services import mail_service

    captured: dict = {}

    class _FakeFastMail:
        def __init__(self, conf):
            captured["conf"] = conf

        async def send_message(self, message):
            captured["message"] = message

    monkeypatch.setattr(mail_service, "ConnectionConfig", lambda **kwargs: kwargs)
    monkeypatch.setattr(mail_service, "FastMail", _FakeFastMail)
    monkeypatch.setenv("MAIL_FROM", "override@example.com")
    service = mail_service.MailService()
    monkeypatch.setattr(service, "is_enabled", lambda: True)

    run_async(service._send_html(subject="test", recipients=["user@example.com"], body="<p>body</p>"))

    assert captured["conf"]["MAIL_FROM"] == "noreply@as.edu.tw"


def test_send_test_email_uses_hardcoded_mail_from(monkeypatch):
    from scripts import send_test_email

    captured: dict = {}

    class _FakeFastMail:
        def __init__(self, conf):
            captured["conf"] = conf

        async def send_message(self, message):
            captured["message"] = message

    monkeypatch.setenv("MAIL_ENABLED", "true")
    monkeypatch.setenv("MAIL_SERVER", "smtp.example.internal")
    monkeypatch.setenv("MAIL_FROM", "override@example.com")
    monkeypatch.setattr(send_test_email, "ConnectionConfig", lambda **kwargs: kwargs)
    monkeypatch.setattr(send_test_email, "FastMail", _FakeFastMail)

    run_async(send_test_email.send_test_email("user@example.com"))

    assert captured["conf"]["MAIL_FROM"] == "noreply@as.edu.tw"

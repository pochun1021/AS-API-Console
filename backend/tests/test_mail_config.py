from __future__ import annotations

from asyncio import run as run_async


def test_mail_service_uses_hardcoded_mail_from(monkeypatch):
    from app.services import mail_service

    captured: dict = {}

    async def _fake_send_html_message(config, *, subject, recipients, body):
        captured["config"] = config
        captured["subject"] = subject
        captured["recipients"] = recipients
        captured["body"] = body

    monkeypatch.setattr(mail_service, "send_html_message", _fake_send_html_message)
    monkeypatch.setenv("MAIL_FROM", "override@example.com")
    service = mail_service.MailService()
    monkeypatch.setattr(service, "is_enabled", lambda: True)

    run_async(service._send_html(subject="test", recipients=["user@example.com"], body="<p>body</p>"))

    assert captured["config"].from_email == "noreply@as.edu.tw"


def test_send_test_email_uses_hardcoded_mail_from(monkeypatch):
    from scripts import send_test_email

    captured: dict = {}

    async def _fake_send_html_message(config, *, subject, recipients, body):
        captured["config"] = config
        captured["subject"] = subject
        captured["recipients"] = recipients
        captured["body"] = body

    monkeypatch.setenv("MAIL_ENABLED", "true")
    monkeypatch.setenv("MAIL_SERVER", "smtp.example.internal")
    monkeypatch.setenv("MAIL_FROM", "override@example.com")
    monkeypatch.setattr(send_test_email, "send_html_message", _fake_send_html_message)

    run_async(send_test_email.send_test_email("user@example.com"))

    assert captured["config"].from_email == "noreply@as.edu.tw"

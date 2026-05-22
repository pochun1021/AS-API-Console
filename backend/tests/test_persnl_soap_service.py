from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.persnl_soap_service import PersnlSoapService


def test_initialize_marks_logged_in(monkeypatch):
    service = PersnlSoapService()
    service.url = "https://example.com/soap"
    service.wsdl_url = None
    service.user = "u"
    service.password = "p"
    monkeypatch.setattr(PersnlSoapService, "_soap_call", lambda self, method, params: "0")

    service.initialize()

    assert service.logged_in is True
    assert service.unavailable_reason is None
    assert service.last_login_at is not None


def test_initialize_marks_unavailable_on_failed_login(monkeypatch):
    service = PersnlSoapService()
    service.url = "https://example.com/soap"
    service.wsdl_url = None
    service.user = "u"
    service.password = "p"
    monkeypatch.setattr(PersnlSoapService, "_soap_call", lambda self, method, params: "1")

    service.initialize()

    assert service.logged_in is False
    assert service.unavailable_reason == "soap login failed"


def test_app_startup_initializes_service(monkeypatch):
    called = {"ok": False}

    def fake_initialize(self):
        called["ok"] = True

    monkeypatch.setattr(PersnlSoapService, "initialize", fake_initialize)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.persnl_soap_service.initialize()
        yield

    app = FastAPI(lifespan=lifespan)
    app.state.persnl_soap_service = PersnlSoapService()

    with TestClient(app):
        pass

    assert called["ok"] is True

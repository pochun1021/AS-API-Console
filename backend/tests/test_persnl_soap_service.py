from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.services.persnl_soap_service import PersnlSoapService, PersnlSoapUnavailableError


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


def test_get_institutes_parses_payload(monkeypatch):
    service = PersnlSoapService()
    service.url = "https://example.com/soap"
    service.user = "u"
    service.password = "p"
    service.logged_in = True
    monkeypatch.setattr(
        PersnlSoapService,
        "_soap_call",
        lambda self, method, params: (
            '{"01":{"instCode":"01","instName":"院本部","abb_instName":"院本部","einstName":"HQ","division":"1"}}'
        ),
    )

    result = service.get_institutes()

    assert result == [
        {
            "instCode": "01",
            "instName": "院本部",
            "abb_instName": "院本部",
            "einstName": "HQ",
            "division": "1",
        }
    ]


def test_query_auto_initializes_when_not_logged_in(monkeypatch):
    service = PersnlSoapService()
    service.url = "https://example.com/soap"
    service.user = "u"
    service.password = "p"
    service.logged_in = False

    calls: list[str] = []

    def fake_soap_call(self, method, params):
        calls.append(method)
        if method == "login":
            return "0"
        return '[{"sysId":"1001","cn":"admin","chName":"Admin","email":"admin@example.com","instCode":"01","tCode":"A01"}]'

    monkeypatch.setattr(PersnlSoapService, "_soap_call", fake_soap_call)
    result = service.search_person_by_account("admin")
    assert result and result[0]["cn"] == "admin"
    assert calls[0] == "login"
    assert calls[1] == "Persnl.getUserAttributes"


def test_query_raises_when_initialize_fails(monkeypatch):
    service = PersnlSoapService()
    service.url = "https://example.com/soap"
    service.user = "u"
    service.password = "p"
    service.logged_in = False

    monkeypatch.setattr(PersnlSoapService, "_soap_call", lambda self, method, params: "1")

    with pytest.raises(PersnlSoapUnavailableError):
        service.search_person_by_account("admin")

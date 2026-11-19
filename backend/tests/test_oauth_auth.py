"""Callback integration with in-memory FISA and DataHub endpoints."""

import base64
import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner

from app.core.config import Settings, get_settings
from app.core.security import rate_limiter
from app.services.datahub_client import DataHubClient
from app.services.oauth_service import OAuthService


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("ALLOWED_HOSTS", "testserver")
    monkeypatch.setenv("SESSION_SECRET_KEY", "fixture-session-secret-with-32-chars")
    get_settings.cache_clear()
    from app.main import create_app
    from app.api import auth
    from db.session import get_db

    allowed = set()
    audit_events = []
    monkeypatch.setattr(auth, "AuthAuditService", lambda db: SimpleNamespace(log=lambda **kwargs: audit_events.append(kwargs)))
    monkeypatch.setattr(auth, "SQLAlchemyWhitelistRepository", lambda db: SimpleNamespace(find_active_by_sysid=lambda sysid: object() if "whitelist" in allowed else None))
    monkeypatch.setattr(auth, "SQLAlchemyAdminRepository", lambda db: SimpleNamespace(get_active_by_id=lambda sysid: object() if "admin" in allowed else None))
    app = create_app()
    app.dependency_overrides[get_db] = lambda: object()
    rate_limiter.reset()
    test_client = TestClient(app, base_url="https://testserver")
    test_client.allow_sources = allowed
    test_client.audit_events = audit_events
    yield test_client
    test_client.close()
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def clear_settings_after_test():
    yield
    get_settings.cache_clear()


def _identity(raw="00123"):
    return {
        "cn": "test.user", "chName": "測試使用者", "email": "test@example.com",
        "instCode": "IT", "sysid": raw, "tCode": "RS01",
    }


def test_production_cannot_enable_header_auth():
    assert Settings.model_construct(app_env="prod", allow_header_auth=True).header_auth_enabled is False


@pytest.mark.parametrize("secret", [
    "dev-session-secret-change-me",
    "replace-with-strong-session-secret",
    "too-short",
])
def test_production_rejects_weak_session_secret(secret):
    with pytest.raises(ValueError, match="SESSION_SECRET_KEY"):
        Settings(app_env="prod", database_url="sqlite+pysqlite:///:memory:", session_secret_key=secret)


def _mock_services(monkeypatch, *, listing=None, token_status=200, token_timeout=False, identity=None, datahub_error=False):
    if listing is None:
        listing = []
    if identity is None:
        identity = _identity()
    calls = []

    def fisa(request):
        calls.append(request.url.path)
        if request.url.path == "/token":
            if token_timeout:
                raise httpx.ReadTimeout("fixture timeout")
            return httpx.Response(token_status, json={"access_token": "fixture-access-token"})
        return httpx.Response(200, json=identity)

    def datahub(request):
        calls.append(request.url.path)
        if datahub_error:
            raise httpx.ReadTimeout("fixture timeout")
        if request.url.path == "/token":
            return httpx.Response(200, json={"accessToken": "fixture-datahub-token"})
        return httpx.Response(200, json=listing)

    oauth_init = OAuthService.__init__
    hub_init = DataHubClient.__init__
    monkeypatch.setattr(OAuthService, "__init__", lambda self: oauth_init(self, transport=httpx.MockTransport(fisa)))
    monkeypatch.setattr(DataHubClient, "__init__", lambda self: hub_init(self, transport=httpx.MockTransport(datahub)))
    monkeypatch.setattr("app.services.oauth_service.validate_outbound_url", lambda value, **_: value)
    monkeypatch.setattr("app.services.datahub_client.validate_outbound_url", lambda value, **_: value)
    return calls


def _env(monkeypatch, *, confirmed=True, allowed_titles="RS01"):
    values = {
        "APP_ENV": "prod", "APP_DOMAIN": "https://api.ascs.sinica.edu.tw/main",
        "OAUTH_AUTH_URI": "https://fisa.example/authorize",
        "OAUTH_TOKEN_URI": "https://fisa.example/token",
        "OAUTH_BASIC_URI": "https://fisa.example/basic",
        "OAUTH_CLIENT_ID": "fixture-client", "OAUTH_CLIENT_SECRET": "fixture-secret",
        "FISA_SYSID_IS_DATAHUB_SSO_CONFIRMED": str(confirmed).lower(),
        "DATAHUB_TOKEN_URL": "https://datahub.example/token",
        "DATAHUB_LIST_URL": "https://datahub.example/list",
        "DATAHUB_CLIENT_ID": "fixture-hub", "DATAHUB_CLIENT_SECRET": "fixture-hub-secret",
        "DATAHUB_LIST_METHOD": "GET", "LOGIN_ALLOWED_TITLE_CODES": allowed_titles,
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()


def _callback(client, *, code="fixture-code", state=None):
    login = client.get("/main/login", follow_redirects=False)
    assert login.status_code == 302
    issued_state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
    query = urlencode({"code": code, "state": issued_state if state is None else state})
    return client.get(f"/main/auth/callback?{query}", follow_redirects=False)


def _item(raw="00123"):
    return {"sso": raw, "name": "fixture", "phone": "", "email": "", "instName": "fixture"}


def _assert_no_auth(client):
    assert "auth_context" not in _session(client)


def _session(client):
    cookie = client.cookies.get(get_settings().session_cookie_name)
    if not cookie:
        return {}
    payload = TimestampSigner(get_settings().session_secret_key).unsign(cookie.encode())
    return json.loads(base64.b64decode(payload))


def test_fisa_success_and_exact_string_match(client, monkeypatch):
    _env(monkeypatch)
    calls = _mock_services(monkeypatch, listing=[_item("123")])
    response = _callback(client)
    assert response.status_code == 302
    assert response.headers["location"] == "/main/announcements"
    assert calls == ["/token", "/basic", "/token", "/list"]
    assert _session(client)["auth_context"]["raw_sysid"] == "00123"
    assert client.audit_events == [{
        "provider": "fisa", "request_id": client.audit_events[0]["request_id"], "result": "success",
    }]


def test_relogin_training_denial_invalidates_previous_auth(client, monkeypatch):
    _env(monkeypatch)
    listing = []
    _mock_services(monkeypatch, listing=listing)
    assert _callback(client).headers["location"] == "/main/announcements"
    assert "auth_context" in _session(client)
    listing.append(_item())
    response = _callback(client)
    assert response.headers["location"].endswith("error=TRAINING_INCOMPLETE")
    _assert_no_auth(client)


@pytest.mark.parametrize("state", ["wrong", ""])
def test_state_mismatch_or_missing_clears_session(client, monkeypatch, state):
    _env(monkeypatch)
    calls = _mock_services(monkeypatch)
    response = _callback(client, state=state)
    assert response.status_code == 422
    assert calls == []
    _assert_no_auth(client)


@pytest.mark.parametrize("kwargs", [
    {"token_status": 500}, {"token_timeout": True},
    {"identity": {"cn": "missing-fields"}},
])
def test_fisa_failure_never_creates_session(client, monkeypatch, kwargs):
    _env(monkeypatch)
    _mock_services(monkeypatch, **kwargs)
    response = _callback(client)
    assert response.status_code in {401, 422}
    _assert_no_auth(client)


@pytest.mark.parametrize("allow_source", ["admin", "whitelist", "title"])
def test_training_hit_blocks_every_allow_source(client, monkeypatch, allow_source):
    _env(monkeypatch, allowed_titles="RS01" if allow_source == "title" else "")
    _mock_services(monkeypatch, listing=[_item()])
    client.allow_sources.add(allow_source)
    response = _callback(client)
    assert response.status_code == 302
    assert response.headers["location"].endswith("error=TRAINING_INCOMPLETE")
    _assert_no_auth(client)


def test_empty_list_allows_existing_rules(client, monkeypatch):
    _env(monkeypatch)
    _mock_services(monkeypatch, listing=[])
    assert _callback(client).headers["location"] == "/main/announcements"


@pytest.mark.parametrize("allow_source", ["admin", "whitelist"])
def test_existing_allow_sources_apply_after_training_miss(client, monkeypatch, allow_source):
    _env(monkeypatch, allowed_titles="")
    _mock_services(monkeypatch, listing=[])
    client.allow_sources.add(allow_source)
    assert _callback(client).headers["location"] == "/main/announcements"
    assert _session(client)["auth_context"]["sysid"] == 123


def test_logout_clears_fisa_session(client, monkeypatch):
    _env(monkeypatch)
    _mock_services(monkeypatch, listing=[])
    assert _callback(client).headers["location"] == "/main/announcements"
    assert "auth_context" in _session(client)
    csrf = _session(client)["csrf_token"]
    response = client.post("/main/logout", headers={"x-csrf-token": csrf})
    assert response.status_code == 200
    _assert_no_auth(client)


@pytest.mark.parametrize("kwargs", [{"datahub_error": True}, {"listing": {"errMsg": "failed"}}])
def test_datahub_failure_is_distinct_and_fail_closed(client, monkeypatch, kwargs):
    _env(monkeypatch)
    _mock_services(monkeypatch, **kwargs)
    response = _callback(client)
    assert response.headers["location"].endswith("error=TRAINING_SERVICE_UNAVAILABLE")
    _assert_no_auth(client)


def test_unconfirmed_mapping_blocks_login_before_datahub(client, monkeypatch):
    _env(monkeypatch, confirmed=False)
    calls = _mock_services(monkeypatch)
    response = _callback(client)
    assert response.headers["location"].endswith("error=TRAINING_SERVICE_UNAVAILABLE")
    assert calls == ["/token", "/basic"]
    _assert_no_auth(client)

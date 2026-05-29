from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from urllib.parse import parse_qs, urlparse

from app.core.errors import ApiError
from app.services.oauth_service import OAuthIdentity
from app.core.config import get_settings
from db.models.auth_audit_logs import AuthAuditLog
from tests.conftest import build_headers


def _set_prod_oauth_env(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "prod")
    get_settings.cache_clear()


def _latest_auth_audit() -> AuthAuditLog | None:
    settings = get_settings()
    db_url = settings.test_database_url or settings.database_url
    engine = create_engine(db_url, future=True)
    with Session(engine) as session:
        return session.query(AuthAuditLog).order_by(AuthAuditLog.created_at.desc()).first()


def test_login_redirects_to_provider(client, monkeypatch):
    _set_prod_oauth_env(monkeypatch)
    resp = client.get("/main/login", follow_redirects=False)
    assert resp.status_code == 302
    location = resp.headers["location"]
    parsed = urlparse(location)
    query = parse_qs(parsed.query)
    assert "state" not in query


def test_callback_success_sets_session_and_audits(client, monkeypatch):
    _set_prod_oauth_env(monkeypatch)
    monkeypatch.setattr(
        "app.services.oauth_service.OAuthService.build_login_url",
        lambda self: "https://oauth.example/auth",
    )
    monkeypatch.setattr(
        "app.services.oauth_service.OAuthService.exchange_code_for_token",
        lambda self, code: "token-1",
    )
    monkeypatch.setattr(
        "app.services.oauth_service.OAuthService.fetch_identity",
        lambda self, token: OAuthIdentity(
            account="oauth.user",
            name="OAuth User",
            email="oauth.user@example.com",
            department="IT",
            sysid=3001,
            tcode="RS01",
            role="user",
        ),
    )

    callback = client.get("/main/auth/callback?code=ok-code", follow_redirects=False)
    assert callback.status_code == 302
    assert callback.headers["location"] == "/main/"

    # verify session auth context can be used without headers
    locale_resp = client.get("/main/api/v1/users/preferences/locale")
    assert locale_resp.status_code == 200
    assert locale_resp.json() == {"preferred_locale": None}

    me_resp = client.get("/main/api/v1/users/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["account"] == "oauth.user"
    assert me_resp.json()["role"] == "user"
    assert me_resp.json()["csrf_token"]

    latest = _latest_auth_audit()
    assert latest is not None
    assert latest.result == "success"
    assert latest.account == "oauth.user"
    assert latest.error_code is None


def test_callback_missing_code_returns_error_and_audits(client):
    resp = client.get("/main/auth/callback", follow_redirects=False)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "OAUTH_CODE_MISSING"
    latest = _latest_auth_audit()
    assert latest is not None
    assert latest.result == "failure"
    assert latest.error_code == "OAUTH_CODE_MISSING"


def test_callback_logs_failure_when_token_exchange_fails(client, monkeypatch):
    _set_prod_oauth_env(monkeypatch)
    monkeypatch.setattr(
        "app.services.oauth_service.OAuthService.exchange_code_for_token",
        lambda self, code: (_ for _ in ()).throw(ApiError("OAUTH_TOKEN_EXCHANGE_FAILED", "oauth token exchange failed", 401)),
    )
    resp = client.get("/main/auth/callback?code=bad-code", follow_redirects=False)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "OAUTH_TOKEN_EXCHANGE_FAILED"
    assert "request_id=" in resp.json()["error"]["message"]
    latest = _latest_auth_audit()
    assert latest is not None
    assert latest.result == "failure"
    assert latest.error_code == "OAUTH_TOKEN_EXCHANGE_FAILED"


def test_callback_logs_failure_when_basic_fetch_fails(client, monkeypatch):
    _set_prod_oauth_env(monkeypatch)
    monkeypatch.setattr("app.services.oauth_service.OAuthService.exchange_code_for_token", lambda self, code: "token-1")
    monkeypatch.setattr(
        "app.services.oauth_service.OAuthService.fetch_identity",
        lambda self, token: (_ for _ in ()).throw(ApiError("OAUTH_BASIC_FETCH_FAILED", "oauth basic profile fetch failed", 401)),
    )
    resp = client.get("/main/auth/callback?code=bad-code", follow_redirects=False)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "OAUTH_BASIC_FETCH_FAILED"
    assert "request_id=" in resp.json()["error"]["message"]
    latest = _latest_auth_audit()
    assert latest is not None
    assert latest.result == "failure"
    assert latest.error_code == "OAUTH_BASIC_FETCH_FAILED"


def test_callback_unexpected_error_returns_controlled_500_and_audits(client, monkeypatch):
    _set_prod_oauth_env(monkeypatch)
    monkeypatch.setattr("app.services.oauth_service.OAuthService.exchange_code_for_token", lambda self, code: "token-1")
    monkeypatch.setattr(
        "app.services.oauth_service.OAuthService.fetch_identity",
        lambda self, token: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    resp = client.get("/main/auth/callback?code=bad-code", follow_redirects=False)
    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "request_id=" in body["error"]["message"]
    latest = _latest_auth_audit()
    assert latest is not None
    assert latest.result == "failure"
    assert latest.error_code == "INTERNAL_ERROR"


def test_callback_allows_missing_state(client, monkeypatch):
    _set_prod_oauth_env(monkeypatch)
    monkeypatch.setattr(
        "app.services.oauth_service.OAuthService.build_login_url",
        lambda self: "https://oauth.example/auth",
    )
    monkeypatch.setattr(
        "app.services.oauth_service.OAuthService.exchange_code_for_token",
        lambda self, code: "token-1",
    )
    monkeypatch.setattr(
        "app.services.oauth_service.OAuthService.fetch_identity",
        lambda self, token: OAuthIdentity(
            account="oauth.user.statefree",
            name="OAuth User Statefree",
            email="oauth.user.statefree@example.com",
            department="IT",
            sysid=3301,
            tcode="RS01",
            role="user",
        ),
    )
    callback = client.get("/main/auth/callback?code=ok-code", follow_redirects=False)
    assert callback.status_code == 302
    assert callback.headers["location"] == "/main/"


def test_callback_allows_any_valid_oauth_identity(client, monkeypatch):
    _set_prod_oauth_env(monkeypatch)
    monkeypatch.setattr(
        "app.services.oauth_service.OAuthService.build_login_url",
        lambda self: "https://oauth.example/auth",
    )
    monkeypatch.setattr("app.services.oauth_service.OAuthService.exchange_code_for_token", lambda self, code: "token-1")
    monkeypatch.setattr(
        "app.services.oauth_service.OAuthService.fetch_identity",
        lambda self, token: OAuthIdentity(
            account="oauth.user2",
            name="OAuth User2",
            email="oauth.user2@example.com",
            department="IT",
            sysid=3002,
            tcode="A001",
            role="user",
        ),
    )
    callback = client.get("/main/auth/callback?code=ok-code", follow_redirects=False)
    assert callback.status_code == 302
    assert callback.headers["location"] == "/main/"


def test_session_mutation_requires_csrf_token(client, monkeypatch):
    _set_prod_oauth_env(monkeypatch)
    monkeypatch.setattr(
        "app.services.oauth_service.OAuthService.build_login_url",
        lambda self: "https://oauth.example/auth",
    )
    monkeypatch.setattr(
        "app.services.oauth_service.OAuthService.exchange_code_for_token",
        lambda self, code: "token-1",
    )
    monkeypatch.setattr(
        "app.services.oauth_service.OAuthService.fetch_identity",
        lambda self, token: OAuthIdentity(
            account="oauth.user4",
            name="OAuth User4",
            email="oauth.user4@example.com",
            department="IT",
            sysid=3004,
            tcode="A100",
            role="user",
        ),
    )
    callback = client.get("/main/auth/callback?code=ok-code", follow_redirects=False)
    assert callback.status_code == 302

    no_csrf = client.patch("/main/api/v1/users/preferences/locale", json={"preferred_locale": "en"})
    assert no_csrf.status_code == 403
    assert no_csrf.json()["error"]["code"] == "FORBIDDEN"


def test_production_rejects_header_only_auth(client, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("ALLOW_HEADER_AUTH", "false")
    headers = build_headers(role="user", account="prod.user", email="prod.user@example.com", sysid=9001)
    resp = client.get("/main/api/v1/users/me", headers=headers)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"
    get_settings.cache_clear()


def test_test_session_login_bootstraps_session_and_csrf(client):
    resp = client.post(
        "/main/test/session-login",
        json={
            "account": "test.admin",
            "name": "Test Admin",
            "email": "test.admin@example.com",
            "department": "Security",
            "sysid": 930001,
            "role": "admin",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "admin"
    assert body["csrf_token"]

    me = client.get("/main/api/v1/users/me")
    assert me.status_code == 200
    assert me.json()["account"] == "test.admin"
    assert me.json()["role"] == "admin"


def test_login_bypasses_oauth_in_dev(client, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("DEV_LOGIN_ACCOUNT", "dev.user")
    monkeypatch.setenv("DEV_LOGIN_NAME", "Dev User")
    monkeypatch.setenv("DEV_LOGIN_EMAIL", "dev.user@example.com")
    monkeypatch.setenv("DEV_LOGIN_DEPARTMENT", "IT")
    monkeypatch.setenv("DEV_LOGIN_SYSID", "990001")
    monkeypatch.setenv("DEV_LOGIN_ROLE", "admin")
    get_settings.cache_clear()

    resp = client.get("/main/login", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/main/"

    me_resp = client.get("/main/api/v1/users/me")
    assert me_resp.status_code == 200
    body = me_resp.json()
    assert body["account"] == "dev.user"
    assert body["sysid"] == 990001
    assert body["role"] == "admin"
    assert body["csrf_token"]


def test_login_bypasses_oauth_in_test(client, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DEV_LOGIN_ACCOUNT", "test.user")
    monkeypatch.setenv("DEV_LOGIN_NAME", "Test User")
    monkeypatch.setenv("DEV_LOGIN_EMAIL", "test.user@example.com")
    monkeypatch.setenv("DEV_LOGIN_DEPARTMENT", "QA")
    monkeypatch.setenv("DEV_LOGIN_SYSID", "990002")
    monkeypatch.setenv("DEV_LOGIN_ROLE", "user")
    get_settings.cache_clear()

    resp = client.get("/main/login", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/main/"

    me_resp = client.get("/main/api/v1/users/me")
    assert me_resp.status_code == 200
    body = me_resp.json()
    assert body["account"] == "test.user"
    assert body["sysid"] == 990002
    assert body["role"] == "user"


def test_login_returns_500_when_dev_login_config_missing(client, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("DEV_LOGIN_ACCOUNT", "")
    monkeypatch.setenv("DEV_LOGIN_NAME", "")
    monkeypatch.setenv("DEV_LOGIN_EMAIL", "")
    monkeypatch.setenv("DEV_LOGIN_DEPARTMENT", "")
    monkeypatch.setenv("DEV_LOGIN_SYSID", "990099")
    get_settings.cache_clear()

    resp = client.get("/main/login", follow_redirects=False)
    assert resp.status_code == 500
    assert resp.json()["error"]["code"] == "INTERNAL_ERROR"


def test_login_returns_500_when_dev_login_role_invalid(client, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("DEV_LOGIN_ACCOUNT", "dev.user")
    monkeypatch.setenv("DEV_LOGIN_NAME", "Dev User")
    monkeypatch.setenv("DEV_LOGIN_EMAIL", "dev.user@example.com")
    monkeypatch.setenv("DEV_LOGIN_DEPARTMENT", "IT")
    monkeypatch.setenv("DEV_LOGIN_SYSID", "990003")
    monkeypatch.setenv("DEV_LOGIN_ROLE", "superuser")
    get_settings.cache_clear()

    resp = client.get("/main/login", follow_redirects=False)
    assert resp.status_code == 500
    assert resp.json()["error"]["code"] == "INTERNAL_ERROR"

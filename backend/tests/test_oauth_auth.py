from fastapi.testclient import TestClient
from urllib.parse import parse_qs, urlparse

from app.core.errors import ApiError
from app.main import app
from app.services.oauth_service import OAuthIdentity
from app.core.config import get_settings
from db.models.admins import Admin
from db.models.auth_audit_logs import AuthAuditLog
from db.models.whitelist import ApiKeyWhitelist
from tests.conftest import build_headers
from tests.db_runtime import session_scope


def _set_prod_oauth_env(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv(
        "LOGIN_ALLOWED_TITLE_CODES",
        "A01,A02,A03,A06,A11,A15,A1A,A1I,B01,B02,B03,B03,B04,B11,B12,B13,B14,B21",
    )
    get_settings.cache_clear()


def _latest_auth_audit() -> AuthAuditLog | None:
    with session_scope() as session:
        return session.query(AuthAuditLog).order_by(AuthAuditLog.created_at.desc()).first()


def _insert_whitelist(sysid: int) -> None:
    with session_scope() as session:
        session.add(
            ApiKeyWhitelist(
                id=f"wl-{sysid}",
                sysid=sysid,
                email=f"wl{sysid}@example.com",
                status="active",
                note=None,
                created_by="test",
                updated_by="test",
            )
        )
        session.commit()


def _insert_admin(admin_id: int) -> None:
    with session_scope() as session:
        session.add(
            Admin(
                id=admin_id,
                account=f"admin{admin_id}",
                email=f"admin{admin_id}@example.com",
                name=f"Admin {admin_id}",
                department="IT",
                status="active",
                created_by="test",
                updated_by="test",
            )
        )
        session.commit()


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
            tcode="A01",
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


def test_callback_unexpected_error_returns_controlled_401_and_audits(client, monkeypatch):
    _set_prod_oauth_env(monkeypatch)
    monkeypatch.setattr(
        "app.services.oauth_service.OAuthService.exchange_code_for_token",
        lambda self, code: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    resp = client.get("/main/auth/callback?code=bad-code", follow_redirects=False)
    assert resp.status_code == 302
    parsed = urlparse(resp.headers["location"])
    assert parsed.path == "/main/login-error"
    query = parse_qs(parsed.query)
    assert query["route"] == ["auth_callback"]
    assert query["reason"] == ["oauth_exchange_failed"]
    assert query["request_id"]
    latest = _latest_auth_audit()
    assert latest is None


def test_callback_unexpected_eligibility_error_redirects_to_login_error(client, monkeypatch):
    _set_prod_oauth_env(monkeypatch)
    monkeypatch.setattr("app.services.oauth_service.OAuthService.exchange_code_for_token", lambda self, code: "token-1")
    monkeypatch.setattr(
        "app.services.oauth_service.OAuthService.fetch_identity",
        lambda self, token: OAuthIdentity(
            account="oauth.user5",
            name="OAuth User5",
            email="oauth.user5@example.com",
            department="IT",
            sysid=3005,
            tcode="A03",
            role="user",
        ),
    )
    monkeypatch.setattr(
        "app.services.login_eligibility_service.LoginEligibilityService.is_eligible",
        lambda self, sysid, tcode: (_ for _ in ()).throw(RuntimeError("db stale connection")),
    )
    resp = client.get("/main/auth/callback?code=bad-code", follow_redirects=False)
    assert resp.status_code == 302
    parsed = urlparse(resp.headers["location"])
    assert parsed.path == "/main/login-error"
    query = parse_qs(parsed.query)
    assert query["route"] == ["auth_callback"]
    assert query["reason"] == ["eligibility_check_failed"]
    assert query["request_id"]
    latest = _latest_auth_audit()
    assert latest is None


def test_login_unexpected_error_redirects_to_login_error(client, monkeypatch):
    _set_prod_oauth_env(monkeypatch)
    monkeypatch.setattr(
        "app.services.oauth_service.OAuthService.build_login_url",
        lambda self: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    resp = client.get("/main/login", follow_redirects=False)
    assert resp.status_code == 302
    parsed = urlparse(resp.headers["location"])
    assert parsed.path == "/main/login-error"
    query = parse_qs(parsed.query)
    assert query["route"] == ["login"]
    assert query["reason"] == ["login_redirect_failed"]
    assert query["request_id"]


def test_users_me_unexpected_error_returns_structured_500(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.core.auth._resolve_admin_role",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    with TestClient(app, raise_server_exceptions=False) as error_client:
        resp = error_client.get(
            "/main/api/v1/users/me",
            headers=build_headers(role="user", account="user1", email="user1@example.com", sysid=2001),
        )
    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert body["error"]["message"] == "unexpected internal error"
    assert body["request_id"]
    assert body["route"] == "/main/api/v1/users/me"
    assert body["reason"] == "unexpected_internal_error"


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
            tcode="A02",
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
    assert callback.headers["location"] == "/main/login-denied?error=LOGIN_NOT_ELIGIBLE"


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
            tcode="A03",
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


def test_callback_allows_when_sysid_in_active_whitelist(client, monkeypatch):
    _set_prod_oauth_env(monkeypatch)
    _insert_whitelist(3888)
    monkeypatch.setattr("app.services.oauth_service.OAuthService.exchange_code_for_token", lambda self, code: "token-1")
    monkeypatch.setattr(
        "app.services.oauth_service.OAuthService.fetch_identity",
        lambda self, token: OAuthIdentity(
            account="oauth.wl",
            name="OAuth WL",
            email="oauth.wl@example.com",
            department="IT",
            sysid=3888,
            tcode="ZZZ",
            role="user",
        ),
    )
    callback = client.get("/main/auth/callback?code=ok-code", follow_redirects=False)
    assert callback.status_code == 302
    assert callback.headers["location"] == "/main/"


def test_callback_allows_when_sysid_matches_active_admin_id(client, monkeypatch):
    _set_prod_oauth_env(monkeypatch)
    _insert_admin(3999)
    monkeypatch.setattr("app.services.oauth_service.OAuthService.exchange_code_for_token", lambda self, code: "token-1")
    monkeypatch.setattr(
        "app.services.oauth_service.OAuthService.fetch_identity",
        lambda self, token: OAuthIdentity(
            account="oauth.admin-id",
            name="OAuth AdminId",
            email="oauth.admin-id@example.com",
            department="IT",
            sysid=3999,
            tcode="ZZZ",
            role="user",
        ),
    )
    callback = client.get("/main/auth/callback?code=ok-code", follow_redirects=False)
    assert callback.status_code == 302
    assert callback.headers["location"] == "/main/"


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
    assert resp.json()["error"]["details"] == "app.api.auth:login"


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
    assert resp.json()["error"]["details"] == "app.api.auth:login"

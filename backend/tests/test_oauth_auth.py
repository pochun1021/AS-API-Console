from app.services.oauth_service import OAuthIdentity
from app.core.config import get_settings
from tests.conftest import build_headers


def test_login_redirects_to_provider(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.oauth_service.OAuthService.build_login_url",
        lambda self, state: f"https://oauth.example/auth?state={state}",
    )
    resp = client.get("/login", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"].startswith("https://oauth.example/auth?state=")


def test_callback_success_sets_session_and_audits(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.oauth_service.OAuthService.build_login_url",
        lambda self, state: f"https://oauth.example/auth?state={state}",
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
            tcode="B123",
            role="user",
        ),
    )

    login = client.get("/login", follow_redirects=False)
    assert login.status_code == 302
    state = login.headers["location"].split("state=")[-1]

    callback = client.get(f"/auth/callback?code=ok-code&state={state}", follow_redirects=False)
    assert callback.status_code == 302
    assert callback.headers["location"] == "/"

    # verify session auth context can be used without headers
    locale_resp = client.get("/api/v1/users/preferences/locale")
    assert locale_resp.status_code == 200
    assert locale_resp.json() == {"preferred_locale": None}

    me_resp = client.get("/api/v1/users/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["account"] == "oauth.user"
    assert me_resp.json()["role"] == "user"
    assert me_resp.json()["csrf_token"]


def test_callback_missing_code_returns_error_and_audits(client):
    resp = client.get("/auth/callback", follow_redirects=False)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "OAUTH_CODE_MISSING"


def test_callback_rejects_not_eligible_login(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.oauth_service.OAuthService.build_login_url",
        lambda self, state: f"https://oauth.example/auth?state={state}",
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
    login = client.get("/login", follow_redirects=False)
    state = login.headers["location"].split("state=")[-1]
    callback = client.get(f"/auth/callback?code=ok-code&state={state}", follow_redirects=False)
    assert callback.status_code == 403
    assert callback.json()["error"]["code"] == "LOGIN_NOT_ELIGIBLE"


def test_callback_allows_non_b_tcode_when_whitelisted(client, monkeypatch):
    admin_headers = build_headers(role="admin", account="admin", email="admin@example.com", sysid="1001")
    white_sysid = 3003
    create_whitelist = client.post(
        "/api/v1/whitelists",
        headers=admin_headers,
        json={"sysid": white_sysid, "note": "seed"},
    )
    assert create_whitelist.status_code == 201

    monkeypatch.setattr(
        "app.services.oauth_service.OAuthService.build_login_url",
        lambda self, state: f"https://oauth.example/auth?state={state}",
    )
    monkeypatch.setattr("app.services.oauth_service.OAuthService.exchange_code_for_token", lambda self, code: "token-1")
    monkeypatch.setattr(
        "app.services.oauth_service.OAuthService.fetch_identity",
        lambda self, token: OAuthIdentity(
            account="oauth.user3",
            name="OAuth User3",
            email="oauth.user3@example.com",
            department="IT",
            sysid=white_sysid,
            tcode="A002",
            role="user",
        ),
    )
    login = client.get("/login", follow_redirects=False)
    state = login.headers["location"].split("state=")[-1]
    callback = client.get(f"/auth/callback?code=ok-code&state={state}", follow_redirects=False)
    assert callback.status_code == 302
    assert callback.headers["location"] == "/"


def test_session_mutation_requires_csrf_token(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.oauth_service.OAuthService.build_login_url",
        lambda self, state: f"https://oauth.example/auth?state={state}",
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
            tcode="B123",
            role="user",
        ),
    )
    login = client.get("/login", follow_redirects=False)
    state = login.headers["location"].split("state=")[-1]
    callback = client.get(f"/auth/callback?code=ok-code&state={state}", follow_redirects=False)
    assert callback.status_code == 302

    no_csrf = client.patch("/api/v1/users/preferences/locale", json={"preferred_locale": "en"})
    assert no_csrf.status_code == 403
    assert no_csrf.json()["error"]["code"] == "FORBIDDEN"


def test_production_rejects_header_only_auth(client, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("ALLOW_HEADER_AUTH", "false")
    headers = build_headers(role="user", account="prod.user", email="prod.user@example.com", sysid=9001)
    resp = client.get("/api/v1/users/me", headers=headers)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"
    get_settings.cache_clear()


def test_test_session_login_bootstraps_session_and_csrf(client):
    resp = client.post(
        "/test/session-login",
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

    me = client.get("/api/v1/users/me")
    assert me.status_code == 200
    assert me.json()["account"] == "test.admin"
    assert me.json()["role"] == "admin"

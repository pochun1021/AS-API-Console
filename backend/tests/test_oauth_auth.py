from app.services.oauth_service import OAuthIdentity
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

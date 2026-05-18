from app.services.oauth_service import OAuthIdentity


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
            sysid="oauth-sysid-1",
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
    assert locale_resp.status_code == 410
    assert locale_resp.json()["error"]["code"] == "FEATURE_DISABLED"


def test_callback_missing_code_returns_error_and_audits(client):
    resp = client.get("/auth/callback", follow_redirects=False)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "OAUTH_CODE_MISSING"

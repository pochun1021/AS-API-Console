from urllib.parse import parse_qs, urlparse

from app.core.config import get_settings


def _reload_settings(monkeypatch, **values):
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()


def test_dev_login_uses_dev_identity_and_dev_path(client, monkeypatch):
    _reload_settings(
        monkeypatch,
        APP_ENV="dev",
        DEV_LOGIN_ACCOUNT="dev.user",
        DEV_LOGIN_NAME="Dev User",
        DEV_LOGIN_EMAIL="dev.user@example.com",
        DEV_LOGIN_DEPARTMENT="IT",
        DEV_LOGIN_SYSID="990001",
        DEV_LOGIN_ROLE="user",
    )

    # The test app is created once with the test path; /main is its fixture
    # compatibility alias while the handler still uses the active APP_ENV.
    response = client.get("/main/login", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/dev/announcements"


def test_test_login_redirects_to_google_and_stores_state(client, monkeypatch):
    _reload_settings(
        monkeypatch,
        APP_ENV="test",
        GOOGLE_CLIENT_ID="google-client-id",
        GOOGLE_CLIENT_SECRET="google-client-secret",
        OAUTH_REDIRECT_URI="http://localhost:8000/test/auth/callback",
    )

    response = client.get("/test/login", follow_redirects=False)

    assert response.status_code == 302
    parsed = urlparse(response.headers["location"])
    query = parse_qs(parsed.query)
    assert parsed.netloc == "accounts.google.com"
    assert query["client_id"] == ["google-client-id"]
    assert query["redirect_uri"] == ["http://localhost:8000/test/auth/callback"]
    assert query["state"]
    assert query["nonce"]


def test_test_api_does_not_accept_header_auth_by_default(client, monkeypatch):
    _reload_settings(monkeypatch, APP_ENV="test", ALLOW_HEADER_AUTH="false")

    response = client.get(
        "/test/api/v1/users/me",
        headers={
            "x-account": "test.user",
            "x-name": "Test User",
            "x-email": "test.user@example.com",
            "x-department": "QA",
            "x-sysid": "990002",
            "x-role": "user",
        },
    )

    assert response.status_code == 401

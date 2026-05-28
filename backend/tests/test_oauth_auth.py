from app.services.oauth_service import OAuthIdentity
from app.core.config import get_settings
from tests.conftest import build_headers


def _set_prod_oauth_env(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "prod")
    get_settings.cache_clear()


def test_login_redirects_to_provider(client, monkeypatch):
    _set_prod_oauth_env(monkeypatch)
    monkeypatch.setattr(
        "app.services.oauth_service.OAuthService.build_login_url",
        lambda self, state: f"https://oauth.example/auth?state={state}",
    )
    resp = client.get("/main/login", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"].startswith("https://oauth.example/auth?state=")


def test_callback_success_sets_session_and_audits(client, monkeypatch):
    _set_prod_oauth_env(monkeypatch)
    monkeypatch.setenv("LOGIN_ALLOWED_TITLE_CODES", "RS01,RS02")
    get_settings.cache_clear()
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
            tcode="RS01",
            role="user",
        ),
    )

    login = client.get("/main/login", follow_redirects=False)
    assert login.status_code == 302
    state = login.headers["location"].split("state=")[-1]

    callback = client.get(f"/main/auth/callback?code=ok-code&state={state}", follow_redirects=False)
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


def test_callback_missing_code_returns_error_and_audits(client):
    resp = client.get("/main/auth/callback", follow_redirects=False)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "OAUTH_CODE_MISSING"


def test_callback_allows_missing_state(client, monkeypatch):
    _set_prod_oauth_env(monkeypatch)
    monkeypatch.setenv("LOGIN_ALLOWED_TITLE_CODES", "RS01")
    get_settings.cache_clear()
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
            account="oauth.user.statefree",
            name="OAuth User Statefree",
            email="oauth.user.statefree@example.com",
            department="IT",
            sysid=3301,
            tcode="RS01",
            role="user",
        ),
    )
    client.get("/main/login", follow_redirects=False)
    callback = client.get("/main/auth/callback?code=ok-code", follow_redirects=False)
    assert callback.status_code == 302
    assert callback.headers["location"] == "/main/"


def test_callback_rejects_not_eligible_login(client, monkeypatch):
    _set_prod_oauth_env(monkeypatch)
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
    login = client.get("/main/login", follow_redirects=False)
    state = login.headers["location"].split("state=")[-1]
    callback = client.get(f"/main/auth/callback?code=ok-code&state={state}", follow_redirects=False)
    assert callback.status_code == 403
    assert callback.json()["error"]["code"] == "LOGIN_NOT_ELIGIBLE"


def test_callback_allows_non_b_tcode_when_whitelisted(client, monkeypatch):
    _set_prod_oauth_env(monkeypatch)
    monkeypatch.setenv("ALLOW_HEADER_AUTH", "true")
    get_settings.cache_clear()
    admin_headers = build_headers(role="admin", account="admin", email="admin@example.com", sysid="1001")
    white_sysid = 3003
    create_whitelist = client.post(
        "/main/api/v1/whitelists",
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
    login = client.get("/main/login", follow_redirects=False)
    state = login.headers["location"].split("state=")[-1]
    callback = client.get(f"/main/auth/callback?code=ok-code&state={state}", follow_redirects=False)
    assert callback.status_code == 302
    assert callback.headers["location"] == "/main/"


def test_session_mutation_requires_csrf_token(client, monkeypatch):
    _set_prod_oauth_env(monkeypatch)
    monkeypatch.setenv("LOGIN_ALLOWED_TITLE_CODES", "A100")
    get_settings.cache_clear()
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
            tcode="A100",
            role="user",
        ),
    )
    login = client.get("/main/login", follow_redirects=False)
    state = login.headers["location"].split("state=")[-1]
    callback = client.get(f"/main/auth/callback?code=ok-code&state={state}", follow_redirects=False)
    assert callback.status_code == 302

    no_csrf = client.patch("/main/api/v1/users/preferences/locale", json={"preferred_locale": "en"})
    assert no_csrf.status_code == 403
    assert no_csrf.json()["error"]["code"] == "FORBIDDEN"


def test_callback_allows_tcode_from_env_case_insensitive(client, monkeypatch):
    _set_prod_oauth_env(monkeypatch)
    monkeypatch.setenv("LOGIN_ALLOWED_TITLE_CODES", " rs01 ,xy9 ")
    get_settings.cache_clear()
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
            account="oauth.user5",
            name="OAuth User5",
            email="oauth.user5@example.com",
            department="IT",
            sysid=3005,
            tcode="RS01",
            role="user",
        ),
    )

    login = client.get("/main/login", follow_redirects=False)
    state = login.headers["location"].split("state=")[-1]
    callback = client.get(f"/main/auth/callback?code=ok-code&state={state}", follow_redirects=False)
    assert callback.status_code == 302
    assert callback.headers["location"] == "/main/"


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
    monkeypatch.delenv("DEV_LOGIN_ACCOUNT", raising=False)
    monkeypatch.delenv("DEV_LOGIN_NAME", raising=False)
    monkeypatch.delenv("DEV_LOGIN_EMAIL", raising=False)
    monkeypatch.delenv("DEV_LOGIN_DEPARTMENT", raising=False)
    monkeypatch.delenv("DEV_LOGIN_SYSID", raising=False)
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

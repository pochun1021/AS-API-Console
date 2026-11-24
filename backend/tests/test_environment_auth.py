from app.core.config import get_settings
from app.services.datahub_client import DataHubError, DataHubErrorKind


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
    assert response.headers["location"] == "/dev/local-login"
    defaults = client.get("/main/auth/local-login")
    assert defaults.status_code == 200
    assert defaults.json()["account"] == "dev.user"
    assert defaults.json()["role"] == "user"


def test_test_login_uses_local_identity_without_fisa(client, monkeypatch):
    _reload_settings(
        monkeypatch,
        APP_ENV="test",
        DEV_LOGIN_ACCOUNT="test.user",
        DEV_LOGIN_NAME="Test User",
        DEV_LOGIN_EMAIL="test.user@example.com",
        DEV_LOGIN_DEPARTMENT="QA",
        DEV_LOGIN_SYSID="990002",
        DEV_LOGIN_ROLE="user",
    )
    checked_sysids = []
    def check_training(_self, *, trusted_sso):
        checked_sysids.append(trusted_sso)
        return False
    monkeypatch.setattr("app.api.auth.TrainingEligibilityService.is_incomplete", check_training)
    def fail_if_fisa_called(*_args, **_kwargs):
        raise AssertionError("test login must not call FISA")

    monkeypatch.setattr("app.services.oauth_service.OAuthService.build_login_url", fail_if_fisa_called)
    response = client.get("/test/login", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/test/local-login"
    defaults = client.get("/test/auth/local-login")
    assert defaults.status_code == 200
    assert defaults.json()["account"] == "test.user"
    assert defaults.json()["sysid"] == 990002
    identity = {**defaults.json(), "account": "another.user", "role": "admin"}
    login = client.post("/test/auth/local-login", json=identity)
    assert login.status_code == 200
    assert checked_sysids == ["990002"]
    assert login.json()["redirect"] == "/test/announcements"
    current_user = client.get("/test/api/v1/users/me")
    assert current_user.status_code == 200
    assert current_user.json()["account"] == "another.user"
    assert current_user.json()["role"] == "admin"

    user_identity = {
        **identity,
        "name": "Edited Name",
        "email": "edited@example.com",
        "department": "Edited Department",
        "sysid": 990003,
        "role": "user",
    }
    assert client.post("/test/auth/local-login", json=user_identity).status_code == 200
    current_user = client.get("/test/api/v1/users/me")
    assert current_user.status_code == 200
    assert {key: current_user.json()[key] for key in user_identity} == user_identity


def test_local_login_handles_datahub_errors_and_incomplete_training(client, monkeypatch):
    _reload_settings(monkeypatch, APP_ENV="test")
    identity = {
        "account": "test.user", "name": "Test User", "email": "test@example.com",
        "department": "QA", "sysid": 990002, "role": "admin",
    }
    checked_sysids = []

    for kind in (DataHubErrorKind.NETWORK, DataHubErrorKind.TIMEOUT):
        def unavailable(_self, *, trusted_sso):
            checked_sysids.append(trusted_sso)
            raise DataHubError(kind)

        monkeypatch.setattr("app.api.auth.TrainingEligibilityService.is_incomplete", unavailable)
        response = client.post("/test/auth/local-login", json=identity)
        assert response.status_code == 200
        assert response.json()["warning"] == "DATAHUB_CONNECTION_FAILED"
        assert client.get("/test/api/v1/users/me").status_code == 200

    def configuration_error(_self, *, trusted_sso):
        checked_sysids.append(trusted_sso)
        raise DataHubError(DataHubErrorKind.CONFIGURATION)

    monkeypatch.setattr("app.api.auth.TrainingEligibilityService.is_incomplete", configuration_error)
    configuration_response = client.post("/test/auth/local-login", json=identity)
    assert configuration_response.status_code == 503
    assert configuration_response.json()["error"]["code"] == "TRAINING_SERVICE_UNAVAILABLE"
    assert client.get("/test/api/v1/users/me").status_code == 401

    def incomplete(_self, *, trusted_sso):
        checked_sysids.append(trusted_sso)
        return True

    monkeypatch.setattr("app.api.auth.TrainingEligibilityService.is_incomplete", incomplete)
    incomplete_response = client.post("/test/auth/local-login", json=identity)
    assert incomplete_response.status_code == 403
    assert incomplete_response.json()["error"]["code"] == "TRAINING_INCOMPLETE"
    assert client.get("/test/api/v1/users/me").status_code == 401
    assert checked_sysids == ["990002"] * 4


def test_local_login_rejects_invalid_identity(client, monkeypatch):
    _reload_settings(monkeypatch, APP_ENV="test")
    response = client.post("/test/auth/local-login", json={
        "account": " ", "name": "Test User", "email": "test.user@example.com",
        "department": "QA", "sysid": 990002, "role": "user",
    })
    assert response.status_code == 422


def test_production_has_no_local_login_endpoints(client, monkeypatch):
    _reload_settings(
        monkeypatch,
        APP_ENV="prod",
        SESSION_SECRET_KEY="production-session-secret-with-at-least-32-characters",
    )
    assert client.get("/main/auth/local-login").status_code == 404
    assert client.post("/main/auth/local-login", json={
        "account": "test.user", "name": "Test User", "email": "test.user@example.com",
        "department": "QA", "sysid": 990002, "role": "user",
    }).status_code == 404
    assert client.post("/main/auth/local-login", json={}).status_code == 404


def test_test_callback_does_not_call_fisa(client, monkeypatch):
    _reload_settings(monkeypatch, APP_ENV="test")

    def fail_if_fisa_called(*_args, **_kwargs):
        raise AssertionError("test callback must not call FISA")

    monkeypatch.setattr("app.services.oauth_service.OAuthService.exchange_code_for_token", fail_if_fisa_called)
    response = client.get("/test/auth/callback?code=fixture&state=fixture", follow_redirects=False)
    assert response.status_code == 404


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

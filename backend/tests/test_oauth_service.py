from types import SimpleNamespace

import pytest

from app.core.config import get_settings
from app.core.config import _resolve_google_client_secrets_file
from app.core.errors import ApiError
from app.services.oauth_service import OAuthService


@pytest.fixture()
def oauth_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    secrets_file = tmp_path / "client_secret.json"
    secrets_file.write_text(
        '{"web":{"client_id":"test-client","client_secret":"test-secret",'
        '"auth_uri":"https://accounts.google.com/o/oauth2/auth",'
        '"token_uri":"https://oauth2.googleapis.com/token"}}'
    )
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRETS_FILE", str(secrets_file))
    monkeypatch.setenv("APP_DOMAIN", "https://console.example/main")
    monkeypatch.setenv("GOOGLE_ALLOWED_HOSTED_DOMAIN", "example.com")
    get_settings.cache_clear()


def test_client_secrets_builds_google_authorization_url(oauth_env) -> None:
    service = OAuthService()
    request = SimpleNamespace(session={})

    url = service.build_login_url(request)

    assert "accounts.google.com" in url
    assert "redirect_uri=https%3A%2F%2Fconsole.example%2Fmain%2Fauth%2Fcallback" in url
    assert request.session["oauth_state"]
    assert request.session["oauth_nonce"]
    assert request.session["oauth_code_verifier"]
    assert f"state={request.session['oauth_state']}" in url
    assert f"nonce={request.session['oauth_nonce']}" in url


def test_client_secret_defaults_to_env_file_directory(monkeypatch, tmp_path) -> None:
    env_file = tmp_path / "config" / ".env"
    env_file.parent.mkdir()
    (env_file.parent / "client_secret.json").write_text("{}")
    monkeypatch.setattr("app.core.config._resolve_env_file", lambda: str(env_file))

    assert _resolve_google_client_secrets_file() == str(env_file.parent / "client_secret.json")


def test_flow_uses_non_persisting_token_updater(oauth_env, monkeypatch) -> None:
    captured = {}

    class FakeFlow:
        redirect_uri = None

    def fake_from_client_secrets_file(filename, scopes, token_updater):  # noqa: ARG001
        captured["token_updater"] = token_updater
        return FakeFlow()

    monkeypatch.setattr(
        "app.services.oauth_service.Flow.from_client_secrets_file",
        fake_from_client_secrets_file,
    )

    service = OAuthService()
    service._new_flow()
    captured["token_updater"]({"access_token": "not persisted"})

    assert callable(captured["token_updater"])


def test_redirect_uri_is_derived_for_current_environment(oauth_env) -> None:
    service = OAuthService()
    service.settings.app_env = "test"
    service.settings.app_domain = "http://localhost:8000/main"

    url = service.build_login_url()

    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Ftest%2Fauth%2Fcallback" in url


def test_exchange_code_failure_is_wrapped(oauth_env, monkeypatch, caplog) -> None:
    class ProviderError(Exception):
        error = "invalid_grant"
        description = "invalid authorization code"

    class FailingFlow:
        credentials = SimpleNamespace(id_token=None)

        def fetch_token(self, **kwargs):  # noqa: ARG002
            raise ProviderError("provider rejected code")

    monkeypatch.setattr(OAuthService, "_new_flow", lambda self: FailingFlow())

    with caplog.at_level("WARNING", logger="app.services.oauth_service"):
        with pytest.raises(ApiError) as exc_info:
            OAuthService().exchange_code_for_token("bad-code", code_verifier="verifier")

    assert exc_info.value.code == "OAUTH_TOKEN_EXCHANGE_FAILED"
    assert "invalid_grant" in caplog.text
    assert "invalid authorization code" in caplog.text


def test_exchange_code_requires_pkce_verifier(oauth_env) -> None:
    with pytest.raises(ApiError, match="code verifier missing"):
        OAuthService().exchange_code_for_token("bad-code")


def test_exchange_code_accepts_google_scope_normalization_warning(oauth_env, monkeypatch, caplog) -> None:
    warning = Warning('Scope has changed from "openid email profile"')
    warning.token = {
        "access_token": "access-token",
        "id_token": "id-token",
        "scope": "openid https://www.googleapis.com/auth/userinfo.email",
        "token_type": "Bearer",
    }
    warning.old_scope = ["openid", "email", "profile"]
    warning.new_scope = ["openid", "https://www.googleapis.com/auth/userinfo.email"]

    class FlowWithScopeWarning:
        code_verifier = None

        class OAuthSession:
            token = {}

        oauth2session = OAuthSession()
        credentials = SimpleNamespace(id_token="id-token")

        def fetch_token(self, **kwargs):  # noqa: ARG002
            raise warning

    monkeypatch.setattr(OAuthService, "_new_flow", lambda self: FlowWithScopeWarning())

    with caplog.at_level("INFO", logger="app.services.oauth_service"):
        token = OAuthService().exchange_code_for_token("code", code_verifier="verifier")

    assert token == "id-token"
    assert "accepted normalized scopes" in caplog.text
    assert "access-token" not in caplog.text


def test_exchange_code_rejects_scope_warning_without_id_token(oauth_env, monkeypatch) -> None:
    warning = Warning("Scope has changed")
    warning.token = {"access_token": "access-token"}

    class FailingFlow:
        def fetch_token(self, **kwargs):  # noqa: ARG002
            raise warning

    monkeypatch.setattr(OAuthService, "_new_flow", lambda self: FailingFlow())

    with pytest.raises(ApiError) as exc_info:
        OAuthService().exchange_code_for_token("code", code_verifier="verifier")

    assert exc_info.value.code == "OAUTH_TOKEN_EXCHANGE_FAILED"


def test_identity_requires_verified_allowed_workspace_and_nonce(oauth_env, monkeypatch) -> None:
    claims = {
        "email": "user@example.com",
        "email_verified": True,
        "hd": "example.com",
        "name": "Example User",
        "nonce": "expected",
    }
    monkeypatch.setattr(
        "app.services.oauth_service.id_token.verify_oauth2_token",
        lambda token, request, audience: claims,  # noqa: ARG005
    )

    identity = OAuthService().fetch_identity("id-token", expected_nonce="expected")

    assert identity.account == "user"
    assert identity.email == "user@example.com"

    with pytest.raises(ApiError, match="nonce"):
        OAuthService().fetch_identity("id-token", expected_nonce="wrong")

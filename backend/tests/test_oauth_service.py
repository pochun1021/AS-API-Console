from types import SimpleNamespace

import pytest

from app.core.config import get_settings
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
    monkeypatch.setenv("OAUTH_REDIRECT_URI", "https://console.example/main/auth/callback")
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
    assert f"state={request.session['oauth_state']}" in url
    assert f"nonce={request.session['oauth_nonce']}" in url


def test_redirect_uri_is_overridden_for_current_environment(oauth_env) -> None:
    service = OAuthService()
    service.settings.oauth_redirect_uri = "http://localhost:8000/test/auth/callback"

    url = service.build_login_url()

    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Ftest%2Fauth%2Fcallback" in url


def test_exchange_code_failure_is_wrapped(oauth_env, monkeypatch) -> None:
    class FailingFlow:
        credentials = SimpleNamespace(id_token=None)

        def fetch_token(self, **kwargs):  # noqa: ARG002
            raise RuntimeError("provider rejected code")

    monkeypatch.setattr(OAuthService, "_new_flow", lambda self: FailingFlow())

    with pytest.raises(ApiError) as exc_info:
        OAuthService().exchange_code_for_token("bad-code")

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

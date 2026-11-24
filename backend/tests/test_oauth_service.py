"""Mock FISA authorization-code and identity endpoint tests."""

from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.core.config import Settings
from app.core.errors import ApiError
from app.services.oauth_service import OAuthService


@pytest.fixture(autouse=True)
def allow_mock_fisa_urls(monkeypatch):
    monkeypatch.setattr("app.services.oauth_service.validate_outbound_url", lambda value, **_: value)


def settings() -> Settings:
    return Settings.model_construct(
        app_env="prod", app_domain="https://console.example/main",
        oauth_auth_uri="https://fisa.example/authorize",
        oauth_token_uri="https://fisa.example/token",
        oauth_basic_uri="https://fisa.example/basic",
        oauth_client_id="fixture-client", oauth_client_secret="fixture-secret",
        oauth_scope="basic", oauth_timeout_seconds=0.5,
        require_https_outbound=True, allow_private_outbound_hosts=False,
    )


def identity(raw_sysid="00123"):
    return {
        "cn": "test.user", "chName": "測試使用者", "email": "test@example.com",
        "instCode": "IT", "sysid": raw_sysid, "tCode": "RS01",
    }


def test_authorization_url_has_login_marker_and_deployment_redirect():
    request = SimpleNamespace(session={}, state=SimpleNamespace(request_id="request-1"))
    url = OAuthService(settings()).build_login_url(request)
    query = parse_qs(urlparse(url).query)
    assert query["response_type"] == ["code"]
    assert query["redirect_uri"] == ["https://console.example/main/auth/callback"]
    assert "state" not in query
    assert request.session["oauth_request_id"] == "request-1"


def test_token_and_identity_use_backend_only_and_preserve_raw_sysid():
    seen = []

    def handler(request):
        seen.append((request.url.path, request.content))
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "fixture-token"})
        return httpx.Response(200, json=identity())

    service = OAuthService(settings(), transport=httpx.MockTransport(handler))
    token = service.exchange_code_for_token("fixture-code")
    person = service.fetch_identity(token)
    assert person.sysid == 123
    assert person.raw_sysid == "00123"
    assert person.account == "test.user"
    assert b"client_secret=fixture-secret" in seen[0][1]
    assert b"access_token=fixture-token" in seen[1][1]


@pytest.mark.parametrize("token_response", [
    httpx.Response(401, json={"errMsg": "failure"}),
    httpx.Response(200, json={"access_token": ""}),
    httpx.Response(200, text="invalid"),
])
def test_token_exchange_failure(token_response):
    service = OAuthService(settings(), transport=httpx.MockTransport(lambda _: token_response))
    with pytest.raises(ApiError, match="oauth token exchange failed"):
        service.exchange_code_for_token("bad-code")


def test_token_timeout():
    def timeout(_):
        raise httpx.ReadTimeout("timeout")

    service = OAuthService(settings(), transport=httpx.MockTransport(timeout))
    with pytest.raises(ApiError) as caught:
        service.exchange_code_for_token("code")
    assert caught.value.code == "OAUTH_TOKEN_EXCHANGE_FAILED"


@pytest.mark.parametrize("claims", [
    [], {"cn": "x"}, {**identity(), "sysid": 123},
    identity("0"), identity("１２３"), {**identity(), "tCode": ""},
])
def test_invalid_fisa_identity(claims):
    service = OAuthService(settings(), transport=httpx.MockTransport(lambda _: httpx.Response(200, json=claims)))
    with pytest.raises(ApiError) as caught:
        service.fetch_identity("token")
    assert caught.value.code == "OAUTH_IDENTITY_INVALID"

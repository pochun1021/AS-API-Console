import logging

import httpx
import pytest

from app.core.config import get_settings
from app.core.errors import ApiError
from app.services.oauth_service import OAuthService


class _FakeClient:
    def __init__(self, response: httpx.Response) -> None:
        self._response = response

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def post(self, url: str, data: dict[str, str]) -> httpx.Response:  # noqa: ARG002
        return self._response


@pytest.fixture()
def oauth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("OAUTH_TOKEN_URI", "https://oauth.example/token")
    monkeypatch.setenv("OAUTH_CLIENT_ID", "test-client")
    monkeypatch.setenv("OAUTH_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("OAUTH_REDIRECT_URI", "https://console.example/main/auth/callback")
    get_settings.cache_clear()


def test_exchange_code_logs_upstream_status_and_body_preview(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    oauth_env: None,  # noqa: ARG001
) -> None:
    req = httpx.Request("POST", "https://oauth.example/token")
    res = httpx.Response(400, request=req, text='{"error":"invalid_grant","error_description":"bad code"}')
    monkeypatch.setattr("app.services.oauth_service.build_safe_httpx_client", lambda timeout_seconds: _FakeClient(res))

    with caplog.at_level(logging.WARNING, logger="app.services.oauth_service"):
        with pytest.raises(ApiError) as exc_info:
            OAuthService().exchange_code_for_token("bad-code")

    assert exc_info.value.code == "OAUTH_TOKEN_EXCHANGE_FAILED"
    assert exc_info.value.message == "oauth token exchange failed: upstream_status=400"
    assert "oauth token exchange upstream failure status=400" in caplog.text
    assert "invalid_grant" in caplog.text

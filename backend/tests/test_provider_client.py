from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.services.provider_client import (
    ProviderBadRequestError,
    ProviderClient,
    ProviderUnavailableError,
    _normalize_provider_base_url,
)


class _FakeClient:
    def __init__(self, response: httpx.Response) -> None:
        self._response = response
        self.calls: list[dict[str, object]] = []

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def post(self, url: str, *, json: dict, headers: dict[str, str]) -> httpx.Response:
        self.calls.append({"url": url, "json": json, "headers": headers})
        return self._response


def _response(payload: object, *, status_code: int = 200) -> httpx.Response:
    request = httpx.Request("POST", "https://provider.internal/test")
    if isinstance(payload, str):
        return httpx.Response(status_code, request=request, text=payload)
    return httpx.Response(status_code, request=request, json=payload)


def test_settings_accepts_https_provider_base_url() -> None:
    settings = Settings(database_url="sqlite://", provider_base_url="https://provider.internal/api")
    assert settings.provider_base_url == "https://provider.internal/api"


def test_settings_rejects_unsupported_provider_base_url_scheme() -> None:
    with pytest.raises(ValidationError, match="PROVIDER_BASE_URL must be a valid http\\(s\\) URL"):
        Settings(database_url="sqlite://", provider_base_url="file:///tmp/provider")


def test_normalize_provider_base_url_rejects_unsupported_scheme() -> None:
    with pytest.raises(ProviderUnavailableError, match="provider base url must use http or https"):
        _normalize_provider_base_url("custom+unix://provider")


def test_provider_client_initialization_rejects_unsafe_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.provider_client.get_settings",
        lambda: SimpleNamespace(
            provider_base_url="file:///tmp/provider",
            provider_master_key="secret",
            provider_timeout_seconds=3.0,
        ),
    )
    with pytest.raises(ProviderUnavailableError, match="provider base url must use http or https"):
        ProviderClient()


def test_provider_client_is_configured_for_https_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.provider_client.get_settings",
        lambda: SimpleNamespace(
            provider_base_url="https://provider.internal/",
            provider_master_key="secret",
            provider_timeout_seconds=3.0,
            provider_debug_logging=False,
        ),
    )
    client = ProviderClient()
    assert client.base_url == "https://provider.internal"
    assert client.master_key == "secret"
    assert client.timeout_seconds == 3.0


def _build_client(monkeypatch: pytest.MonkeyPatch) -> ProviderClient:
    monkeypatch.setattr(
        ProviderClient,
        "is_configured",
        lambda self: bool(self.base_url and self.master_key),
    )
    monkeypatch.setattr(
        "app.services.provider_client.get_settings",
        lambda: SimpleNamespace(
            provider_base_url="https://provider.internal",
            provider_master_key="secret-token",
            provider_timeout_seconds=3.0,
            provider_debug_logging=False,
        ),
    )
    return ProviderClient()


def test_generate_key_uses_bearer_auth_and_reads_key_field(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _build_client(monkeypatch)
    fake_client = _FakeClient(_response({"key": "AS-plain", "request_id": "req-1", "operation_id": "op-1"}))
    captured: dict[str, object] = {}

    def _fake_httpx_client(*, timeout_seconds: float, base_url: str | None = None, follow_redirects: bool = False) -> _FakeClient:
        captured["timeout_seconds"] = timeout_seconds
        captured["base_url"] = base_url
        captured["follow_redirects"] = follow_redirects
        return fake_client

    monkeypatch.setattr("app.services.provider_client.build_safe_httpx_client", _fake_httpx_client)
    result = client.generate_key({"duration": "30d"})

    assert captured == {
        "timeout_seconds": 3.0,
        "base_url": "https://provider.internal",
        "follow_redirects": False,
    }
    assert fake_client.calls == [
        {
            "url": "/key/generate",
            "json": {"duration": "30d"},
            "headers": {
                "Content-Type": "application/json",
                "Authorization": "Bearer secret-token",
            },
        }
    ]
    assert result.key_plaintext == "AS-plain"
    assert result.request_id == "req-1"
    assert result.operation_id == "op-1"


def test_update_team_limits_posts_to_team_bulk_update(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _build_client(monkeypatch)
    fake_client = _FakeClient(_response("ok"))
    monkeypatch.setattr("app.services.provider_client.build_safe_httpx_client", lambda **kwargs: fake_client)

    result = client.update_team_limits(
        {"team_id": "team-1", "all_keys_in_team": True, "update_fields": {"tpm_limit": 10000, "max_parallel_requests": None}}
    )

    assert result.success is True
    assert fake_client.calls == [
        {
            "url": "/team/key/bulk_update",
            "json": {"team_id": "team-1", "all_keys_in_team": True, "update_fields": {"tpm_limit": 10000, "max_parallel_requests": None}},
            "headers": {
                "Content-Type": "application/json",
                "Authorization": "Bearer secret-token",
            },
        }
    ]


def test_update_key_accepts_string_response(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _build_client(monkeypatch)
    monkeypatch.setattr(
        "app.services.provider_client.build_safe_httpx_client",
        lambda **kwargs: _FakeClient(_response("success")),
    )

    result = client.update_key({"key": "AS-old"})
    assert result.success is True
    assert result.request_id is None
    assert result.operation_id is None


def test_provider_422_maps_detail_array(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _build_client(monkeypatch)
    monkeypatch.setattr(
        "app.services.provider_client.build_safe_httpx_client",
        lambda **kwargs: _FakeClient(
            _response(
                {"detail": [{"loc": ["body", "duration"], "msg": "invalid duration", "type": "value_error"}]},
                status_code=422,
            )
        ),
    )

    with pytest.raises(ProviderBadRequestError, match="body.duration: invalid duration"):
        client.generate_key({"duration": "bad"})


def test_provider_missing_key_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _build_client(monkeypatch)
    monkeypatch.setattr(
        "app.services.provider_client.build_safe_httpx_client",
        lambda **kwargs: _FakeClient(_response({"token": "secret"})),
    )

    with pytest.raises(ProviderUnavailableError, match="provider response missing key"):
        client.generate_key({"duration": "30d"})


def test_provider_403_logs_upstream_status_when_debug_enabled(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(
        ProviderClient,
        "is_configured",
        lambda self: bool(self.base_url and self.master_key),
    )
    monkeypatch.setattr(
        "app.services.provider_client.get_settings",
        lambda: SimpleNamespace(
            provider_base_url="https://provider.internal",
            provider_master_key="secret-token",
            provider_timeout_seconds=3.0,
            provider_debug_logging=True,
        ),
    )
    monkeypatch.setattr(
        "app.services.provider_client.build_safe_httpx_client",
        lambda **kwargs: _FakeClient(_response({"detail": "forbidden", "token": "hidden"}, status_code=403)),
    )
    client = ProviderClient()

    with caplog.at_level("INFO"):
        with pytest.raises(ProviderBadRequestError, match="provider rejected request: 403"):
            client.generate_key({"duration": "30d"})

    assert any(record.message == "provider response" and getattr(record, "status_code", None) == 403 for record in caplog.records)
    provider_logs = [record for record in caplog.records if record.message == "provider response"]
    assert provider_logs
    assert getattr(provider_logs[-1], "json_keys", None) == ["detail"]

from types import SimpleNamespace

import pytest
import requests
from pydantic import ValidationError

from app.core.config import Settings
from app.services.provider_client import (
    ProviderBadRequestError,
    ProviderClient,
    ProviderUnavailableError,
    _normalize_provider_base_url,
)


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


class _FakeResponse:
    def __init__(self, payload: object, *, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def json(self) -> object:
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload

    def raise_for_status(self) -> None:
        if self.status_code < 400:
            return
        raise requests.HTTPError(response=self)


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
    captured: dict = {}

    def _fake_post(url, *, json, headers, timeout):
        captured["url"] = url
        captured["auth"] = headers.get("Authorization")
        captured["legacy_auth"] = headers.get("x-master-key")
        captured["body"] = json
        captured["timeout"] = timeout
        return _FakeResponse({"key": "AS-plain", "request_id": "req-1", "operation_id": "op-1"})

    monkeypatch.setattr("app.services.provider_client.requests.post", _fake_post)
    result = client.generate_key({"duration": "30d"})

    assert captured["url"] == "https://provider.internal/key/generate"
    assert captured["auth"] == "Bearer secret-token"
    assert captured["legacy_auth"] is None
    assert captured["body"] == {"duration": "30d"}
    assert captured["timeout"] == 3.0
    assert result.key_plaintext == "AS-plain"
    assert result.request_id == "req-1"
    assert result.operation_id == "op-1"


def test_update_key_accepts_string_response(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _build_client(monkeypatch)

    monkeypatch.setattr(
        "app.services.provider_client.requests.post",
        lambda url, **kwargs: _FakeResponse("success"),
    )

    result = client.update_key({"key": "AS-old"})
    assert result.success is True
    assert result.request_id is None
    assert result.operation_id is None


def test_provider_422_maps_detail_array(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _build_client(monkeypatch)
    monkeypatch.setattr(
        "app.services.provider_client.requests.post",
        lambda url, **kwargs: _FakeResponse(
            {"detail": [{"loc": ["body", "duration"], "msg": "invalid duration", "type": "value_error"}]},
            status_code=422,
        ),
    )

    with pytest.raises(ProviderBadRequestError, match="body.duration: invalid duration"):
        client.generate_key({"duration": "bad"})


def test_provider_missing_key_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _build_client(monkeypatch)

    monkeypatch.setattr(
        "app.services.provider_client.requests.post",
        lambda url, **kwargs: _FakeResponse({"token": "secret"}),
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
        "app.services.provider_client.requests.post",
        lambda url, **kwargs: _FakeResponse({"detail": "forbidden", "token": "hidden"}, status_code=403),
    )
    client = ProviderClient()

    with caplog.at_level("INFO"):
        with pytest.raises(ProviderBadRequestError, match="provider rejected request: 403"):
            client.generate_key({"duration": "30d"})

    assert any(record.message == "provider response" and getattr(record, "status_code", None) == 403 for record in caplog.records)
    provider_logs = [record for record in caplog.records if record.message == "provider response"]
    assert provider_logs
    assert getattr(provider_logs[-1], "json_keys", None) == ["detail"]

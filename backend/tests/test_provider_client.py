import io
from types import SimpleNamespace
from urllib import error

import pytest
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
        ),
    )
    client = ProviderClient()
    assert client.base_url == "https://provider.internal"
    assert client.master_key == "secret"
    assert client.timeout_seconds == 3.0


class _FakeResponse:
    def __init__(self, payload: str) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return self.payload.encode("utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


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
        ),
    )
    return ProviderClient()


def test_generate_key_uses_bearer_auth_and_reads_key_field(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _build_client(monkeypatch)
    captured: dict = {}

    def _fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["auth"] = req.headers.get("Authorization")
        captured["legacy_auth"] = req.headers.get("x-master-key")
        captured["body"] = req.data.decode("utf-8")
        captured["timeout"] = timeout
        return _FakeResponse('{"key":"AS-plain","request_id":"req-1","operation_id":"op-1"}')

    monkeypatch.setattr("app.services.provider_client.request.urlopen", _fake_urlopen)
    result = client.generate_key({"duration": "30d"})

    assert captured["url"] == "https://provider.internal/key/generate"
    assert captured["auth"] == "Bearer secret-token"
    assert captured["legacy_auth"] is None
    assert captured["body"] == '{"duration": "30d"}'
    assert captured["timeout"] == 3.0
    assert result.key_plaintext == "AS-plain"
    assert result.request_id == "req-1"
    assert result.operation_id == "op-1"


def test_update_key_accepts_string_response(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _build_client(monkeypatch)

    monkeypatch.setattr(
        "app.services.provider_client.request.urlopen",
        lambda req, timeout: _FakeResponse('"success"'),
    )

    result = client.update_key({"key": "AS-old"})
    assert result.success is True
    assert result.request_id is None
    assert result.operation_id is None


def test_provider_422_maps_detail_array(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _build_client(monkeypatch)
    payload = b'{"detail":[{"loc":["body","duration"],"msg":"invalid duration","type":"value_error"}]}'

    def _fake_urlopen(req, timeout):
        raise error.HTTPError(
            url=req.full_url,
            code=422,
            msg="unprocessable",
            hdrs=None,
            fp=io.BytesIO(payload),
        )

    monkeypatch.setattr("app.services.provider_client.request.urlopen", _fake_urlopen)

    with pytest.raises(ProviderBadRequestError, match="body.duration: invalid duration"):
        client.generate_key({"duration": "bad"})


def test_provider_missing_key_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _build_client(monkeypatch)

    monkeypatch.setattr(
        "app.services.provider_client.request.urlopen",
        lambda req, timeout: _FakeResponse('{"token":"secret"}'),
    )

    with pytest.raises(ProviderUnavailableError, match="provider response missing key"):
        client.generate_key({"duration": "30d"})

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.services.provider_client import ProviderClient, ProviderUnavailableError, _normalize_provider_base_url


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

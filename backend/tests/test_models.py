from datetime import datetime
from types import SimpleNamespace

import httpx
import pytest

from tests.conftest import api_path
from app.services.models_service import ModelsService
from app.services.provider_client import ProviderUnavailableError


class _ProviderStub:
    def list_models(self):
        return []


def test_models_endpoint_returns_test_data_in_test_mode(client, user_headers):
    resp = client.get(api_path("/models"), headers=user_headers)

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total"] == 2
    assert payload["items"] == [
        {"id": "gpt-4o", "label": "gpt-4o"},
        {"id": "gpt-4o-mini", "label": "gpt-4o-mini"},
    ]
    datetime.fromisoformat(payload["fetched_at"].replace("Z", "+00:00"))


def test_models_endpoint_returns_test_data_for_admin_in_test_mode(client, admin_headers):
    resp = client.get(api_path("/models"), headers=admin_headers)

    assert resp.status_code == 200
    assert resp.json()["items"] == [
        {"id": "gpt-4o", "label": "gpt-4o"},
        {"id": "gpt-4o-mini", "label": "gpt-4o-mini"},
    ]


def test_models_service_normalizes_openai_style_payload():
    service = ModelsService(provider_client=_ProviderStub())

    items = service._normalize_payload({"data": [{"id": "gpt-4o-mini"}, {"id": "gpt-4o"}]})

    assert items == [
        {"id": "gpt-4o", "label": "gpt-4o"},
        {"id": "gpt-4o-mini", "label": "gpt-4o-mini"},
    ]


def test_models_service_normalizes_string_array_payload():
    service = ModelsService(provider_client=_ProviderStub())

    items = service._normalize_payload(["gpt-4o", "gpt-4o-mini"])

    assert items == [
        {"id": "gpt-4o", "label": "gpt-4o"},
        {"id": "gpt-4o-mini", "label": "gpt-4o-mini"},
    ]


def test_models_service_dedupes_filters_blanks_and_sorts():
    service = ModelsService(provider_client=_ProviderStub())

    items = service._normalize_payload({"data": [{"id": " "}, {"id": "gpt-4o"}, {"id": "gpt-4o"}, {"id": "gpt-4o-mini"}]})

    assert items == [
        {"id": "gpt-4o", "label": "gpt-4o"},
        {"id": "gpt-4o-mini", "label": "gpt-4o-mini"},
    ]


def test_models_service_returns_test_data_in_dev_mode():
    service = ModelsService(
        provider_client=_ProviderStub(),
        settings=SimpleNamespace(app_env="dev"),
    )

    payload = service.list_models(current_user=SimpleNamespace(role="user"))

    assert payload["items"] == [
        {"id": "gpt-4o", "label": "gpt-4o"},
        {"id": "gpt-4o-mini", "label": "gpt-4o-mini"},
    ]
    assert payload["total"] == 2


def test_models_service_uses_provider_in_prod_mode():
    class _ProdProviderStub:
        def list_models(self):
            return {"data": [{"id": "gpt-4o-mini"}]}

    service = ModelsService(
        provider_client=_ProdProviderStub(),
        settings=SimpleNamespace(app_env="prod"),
    )

    payload = service.list_models(current_user=SimpleNamespace(role="user"))

    assert payload["items"] == [{"id": "gpt-4o-mini", "label": "gpt-4o-mini"}]
    assert payload["total"] == 1


@pytest.mark.parametrize(
    "failure",
    [
        ProviderUnavailableError("timeout"),
        ProviderUnavailableError("provider unavailable: 503"),
    ],
)
def test_models_endpoint_maps_provider_errors_to_503(client, user_headers, monkeypatch, failure):
    monkeypatch.setattr(
        "app.services.models_service.get_settings",
        lambda: SimpleNamespace(app_env="prod"),
    )

    def raise_error(self):
        raise failure

    monkeypatch.setattr("app.services.models_service.ProviderClient.list_models", raise_error)

    resp = client.get(api_path("/models"), headers=user_headers)

    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"


def test_models_endpoint_maps_unrecognized_payload_to_503(client, user_headers, monkeypatch):
    monkeypatch.setattr(
        "app.services.models_service.get_settings",
        lambda: SimpleNamespace(app_env="prod"),
    )
    monkeypatch.setattr(
        "app.services.models_service.ProviderClient.list_models",
        lambda self: {"unexpected": True},
    )

    resp = client.get(api_path("/models"), headers=user_headers)

    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"


class _FakeReadClient:
    def __init__(self, response: httpx.Response) -> None:
        self._response = response
        self.calls: list[dict[str, object]] = []

    def __enter__(self) -> "_FakeReadClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def get(self, url: str, *, headers: dict[str, str]) -> httpx.Response:
        self.calls.append({"url": url, "headers": headers})
        return self._response


def test_provider_client_list_models_uses_get_without_payload(monkeypatch):
    from types import SimpleNamespace
    from app.services.provider_client import ProviderClient

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
    client = ProviderClient()
    fake_client = _FakeReadClient(
        httpx.Response(
            200,
            request=httpx.Request("GET", "https://provider.internal/models"),
            json={"data": [{"id": "gpt-4o-mini"}]},
        )
    )
    monkeypatch.setattr("app.services.provider_client.build_safe_httpx_client", lambda **kwargs: fake_client)

    result = client.list_models()

    assert result == {"data": [{"id": "gpt-4o-mini"}]}
    assert fake_client.calls == [{"url": "/models", "headers": {"Authorization": "Bearer secret-token"}}]

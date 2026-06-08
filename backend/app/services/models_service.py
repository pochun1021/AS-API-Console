from datetime import UTC, datetime

from app.core.auth import CurrentUser
from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.services.provider_client import ProviderBadRequestError, ProviderClient, ProviderUnavailableError

_TEST_MODELS_PAYLOAD = {
    "data": [
        {
            "id": "gpt-4o",
            "object": "model",
            "created": 1677610602,
            "owned_by": "openai",
        },
        {
            "id": "gpt-4o-mini",
            "object": "model",
            "created": 1677610602,
            "owned_by": "openai",
        },
    ],
    "object": "list",
}


def _normalize_model_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


class ModelsService:
    def __init__(self, provider_client: ProviderClient | None = None, settings: Settings | None = None) -> None:
        self.provider_client = provider_client or ProviderClient()
        self.settings = settings or get_settings()

    def list_models(self, *, current_user: CurrentUser) -> dict:
        _ = current_user
        if self.settings.app_env.lower() in {"dev", "test"}:
            items = self._normalize_payload(_TEST_MODELS_PAYLOAD)
            assert items is not None
            return {
                "items": items,
                "total": len(items),
                "fetched_at": datetime.now(UTC),
            }

        try:
            payload = self.provider_client.list_models()
        except (ProviderUnavailableError, ProviderBadRequestError) as exc:
            raise ApiError("PROVIDER_UNAVAILABLE", "provider unavailable", 503) from exc

        items = self._normalize_payload(payload)
        if items is None:
            raise ApiError("PROVIDER_UNAVAILABLE", "provider unavailable", 503)

        return {
            "items": items,
            "total": len(items),
            "fetched_at": datetime.now(UTC),
        }

    def _normalize_payload(self, payload: object) -> list[dict[str, str]] | None:
        raw_items: list[object] | None = None
        if isinstance(payload, dict) and isinstance(payload.get("data"), list):
            raw_items = payload["data"]
            extractor = self._normalize_from_object
        elif isinstance(payload, list):
            raw_items = payload
            extractor = self._normalize_from_string
        else:
            return None

        seen: set[str] = set()
        items: list[dict[str, str]] = []
        for entry in raw_items:
            normalized = extractor(entry)
            if normalized is None or normalized["id"] in seen:
                continue
            seen.add(normalized["id"])
            items.append(normalized)

        items.sort(key=lambda item: item["id"].lower())
        return items

    def _normalize_from_object(self, entry: object) -> dict[str, str] | None:
        if not isinstance(entry, dict):
            return None
        model_id = _normalize_model_id(entry.get("id"))
        if model_id is None:
            return None
        return {"id": model_id, "label": model_id}

    def _normalize_from_string(self, entry: object) -> dict[str, str] | None:
        model_id = _normalize_model_id(entry)
        if model_id is None:
            return None
        return {"id": model_id, "label": model_id}

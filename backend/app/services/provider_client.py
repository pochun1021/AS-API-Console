import json
import logging
from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.core.outbound import build_safe_httpx_client, validate_outbound_url

logger = logging.getLogger(__name__)
_SENSITIVE_FIELDS = {"authorization", "key", "token"}


@dataclass(slots=True)
class ProviderMutationResult:
    success: bool = True
    request_id: str | None = None
    operation_id: str | None = None


@dataclass(slots=True)
class ProviderGenerateResult:
    key_plaintext: str
    success: bool = True
    request_id: str | None = None
    operation_id: str | None = None


class ProviderUnavailableError(RuntimeError):
    pass


class ProviderBadRequestError(RuntimeError):
    pass


def _extract_validation_message(payload: object) -> str:
    if not isinstance(payload, dict):
        return "provider validation failed"
    details = payload.get("detail")
    if not isinstance(details, list) or not details:
        return "provider validation failed"

    messages: list[str] = []
    for item in details:
        if not isinstance(item, dict):
            continue
        msg = str(item.get("msg") or "").strip()
        if not msg:
            continue
        loc = item.get("loc")
        if isinstance(loc, list):
            loc_path = ".".join(str(part) for part in loc if str(part).strip())
            if loc_path:
                messages.append(f"{loc_path}: {msg}")
                continue
        messages.append(msg)
    return "; ".join(messages) or "provider validation failed"


def _normalize_provider_base_url(base_url: str | None) -> str:
    normalized = (base_url or "").strip()
    if not normalized:
        return ""
    try:
        return validate_outbound_url(normalized, config_name="PROVIDER_BASE_URL").rstrip("/")
    except Exception as exc:
        raise ProviderUnavailableError("provider base url must use http or https") from exc


def _response_summary(payload: object) -> dict[str, object]:
    if isinstance(payload, dict):
        return {"json_keys": sorted(str(key) for key in payload.keys() if str(key).lower() not in _SENSITIVE_FIELDS)}
    if isinstance(payload, list):
        return {"json_type": "list", "items": len(payload)}
    if isinstance(payload, str):
        return {"text_length": len(payload)}
    return {"json_type": type(payload).__name__}


class ProviderClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = _normalize_provider_base_url(settings.provider_base_url)
        self.master_key = settings.provider_master_key or ""
        self.timeout_seconds = settings.provider_timeout_seconds
        self.debug_logging = settings.provider_debug_logging

    def is_configured(self) -> bool:
        return bool(self.base_url and self.master_key)

    def _log_request(self, *, path: str, payload: dict) -> None:
        if not self.debug_logging:
            return
        logger.info(
            "provider request",
            extra={
                "provider_path": path,
                "payload_keys": sorted(payload.keys()),
                "timeout_seconds": self.timeout_seconds,
            },
        )

    def _log_response(
        self,
        *,
        path: str,
        status_code: int,
        payload: object,
        request_id: str | None = None,
        operation_id: str | None = None,
    ) -> None:
        if not self.debug_logging:
            return
        logger.info(
            "provider response",
            extra={
                "provider_path": path,
                "status_code": status_code,
                "request_id": request_id,
                "operation_id": operation_id,
                **_response_summary(payload),
            },
        )

    def _perform_request(
        self,
        *,
        path: str,
        payload: dict,
        require_plaintext: bool = False,
    ) -> ProviderMutationResult:
        if not self.is_configured():
            raise ProviderUnavailableError("provider is not configured")

        self._log_request(path=path, payload=payload)

        try:
            with build_safe_httpx_client(timeout_seconds=self.timeout_seconds, base_url=self.base_url) as client:
                resp = client.post(
                    path,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.master_key}",
                    },
                )
                resp.raise_for_status()
                try:
                    data = resp.json()
                except json.JSONDecodeError:
                    if require_plaintext:
                        raise
                    data = resp.text
        except httpx.HTTPStatusError as exc:
            response_payload: object = {}
            try:
                response_payload = exc.response.json() if exc.response is not None else {}
            except Exception:  # noqa: BLE001
                response_payload = {}
            status_code = exc.response.status_code if exc.response is not None else 0
            self._log_response(path=path, status_code=status_code, payload=response_payload)
            if status_code == 422:
                raise ProviderBadRequestError(_extract_validation_message(response_payload)) from exc
            if 400 <= status_code < 500:
                raise ProviderBadRequestError(f"provider rejected request: {status_code}") from exc
            raise ProviderUnavailableError(f"provider unavailable: {status_code}") from exc
        except (httpx.RequestError, json.JSONDecodeError) as exc:
            raise ProviderUnavailableError("provider unavailable") from exc

        request_id: str | None = None
        operation_id: str | None = None
        if isinstance(data, dict):
            request_id = str(data.get("request_id") or "").strip() or None
            operation_id = str(data.get("operation_id") or "").strip() or None
        self._log_response(
            path=path,
            status_code=resp.status_code,
            payload=data,
            request_id=request_id,
            operation_id=operation_id,
        )
        if not require_plaintext:
            return ProviderMutationResult(success=True, request_id=request_id, operation_id=operation_id)

        plaintext = str(data.get("key") or "").strip() if isinstance(data, dict) else ""
        if not plaintext:
            raise ProviderUnavailableError("provider response missing key")
        return ProviderGenerateResult(
            key_plaintext=plaintext,
            success=True,
            request_id=request_id,
            operation_id=operation_id,
        )

    def generate_key(self, payload: dict) -> ProviderGenerateResult:
        result = self._perform_request(path="/key/generate", payload=payload, require_plaintext=True)
        assert isinstance(result, ProviderGenerateResult)
        return result

    def update_key(self, payload: dict) -> ProviderMutationResult:
        return self._perform_request(path="/key/update", payload=payload)

    def block_key(self, payload: dict) -> ProviderMutationResult:
        return self._perform_request(path="/key/block", payload=payload)

    def update_team_limits(self, payload: dict) -> ProviderMutationResult:
        return self._perform_request(path="/team/key/bulk_update", payload=payload)

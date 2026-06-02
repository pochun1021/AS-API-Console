import json
from dataclasses import dataclass
from urllib import error, request

from app.core.config import get_settings
from app.core.outbound import validate_outbound_url


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


class ProviderClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = _normalize_provider_base_url(settings.provider_base_url)
        self.master_key = settings.provider_master_key or ""
        self.timeout_seconds = settings.provider_timeout_seconds

    def is_configured(self) -> bool:
        return bool(self.base_url and self.master_key)

    def _perform_request(
        self,
        *,
        path: str,
        payload: dict,
        require_plaintext: bool = False,
    ) -> ProviderMutationResult:
        if not self.is_configured():
            raise ProviderUnavailableError("provider is not configured")

        req = request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.master_key}",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:  # nosec B310
                data = json.loads(resp.read().decode("utf-8") or "{}")
        except error.HTTPError as exc:
            response_payload: object = {}
            try:
                response_payload = json.loads(exc.read().decode("utf-8") or "{}")
            except Exception:  # noqa: BLE001
                response_payload = {}
            if exc.code == 422:
                raise ProviderBadRequestError(_extract_validation_message(response_payload)) from exc
            if 400 <= exc.code < 500:
                raise ProviderBadRequestError(f"provider rejected request: {exc.code}") from exc
            raise ProviderUnavailableError(f"provider unavailable: {exc.code}") from exc
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ProviderUnavailableError("provider unavailable") from exc

        request_id: str | None = None
        operation_id: str | None = None
        if isinstance(data, dict):
            request_id = str(data.get("request_id") or "").strip() or None
            operation_id = str(data.get("operation_id") or "").strip() or None
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

    def regenerate_key(self, payload: dict) -> ProviderGenerateResult:
        result = self._perform_request(path="/key/regenerate", payload=payload, require_plaintext=True)
        assert isinstance(result, ProviderGenerateResult)
        return result

    def update_key(self, payload: dict) -> ProviderMutationResult:
        return self._perform_request(path="/key/update", payload=payload)

    def block_key(self, payload: dict) -> ProviderMutationResult:
        return self._perform_request(path="/key/block", payload=payload)

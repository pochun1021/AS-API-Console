from dataclasses import dataclass
from urllib import error, request
import json

from app.core.config import get_settings


@dataclass(slots=True)
class ProviderGenerateResult:
    key_plaintext: str


class ProviderUnavailableError(RuntimeError):
    pass


class ProviderBadRequestError(RuntimeError):
    pass


class ProviderClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = (settings.provider_base_url or "").rstrip("/")
        self.master_key = settings.provider_master_key or ""
        self.timeout_seconds = settings.provider_timeout_seconds

    def is_configured(self) -> bool:
        return bool(self.base_url and self.master_key)

    def generate_key(self, payload: dict) -> ProviderGenerateResult:
        if not self.is_configured():
            raise ProviderUnavailableError("provider is not configured")

        req = request.Request(
            f"{self.base_url}/key/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-master-key": self.master_key,
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8") or "{}")
        except error.HTTPError as exc:
            if 400 <= exc.code < 500:
                raise ProviderBadRequestError(f"provider rejected request: {exc.code}") from exc
            raise ProviderUnavailableError(f"provider unavailable: {exc.code}") from exc
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ProviderUnavailableError("provider unavailable") from exc

        plaintext = str(data.get("api_key_plaintext") or "").strip()
        if not plaintext:
            raise ProviderUnavailableError("provider response missing api_key_plaintext")
        return ProviderGenerateResult(key_plaintext=plaintext)

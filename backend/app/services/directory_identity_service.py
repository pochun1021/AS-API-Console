from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from db.repositories.types import AuthIdentity


class DirectoryLookupNotFoundError(RuntimeError):
    pass


class DirectoryLookupNotUniqueError(RuntimeError):
    pass


class DirectoryLookupUnavailableError(RuntimeError):
    pass


@dataclass(slots=True)
class DirectoryIdentityService:
    api_url: str | None = None
    timeout_seconds: float = 3.0

    def __init__(self) -> None:
        settings = get_settings()
        self.api_url = settings.directory_identity_api_url
        self.timeout_seconds = settings.directory_identity_timeout_seconds

    def is_configured(self) -> bool:
        return bool(self.api_url)

    def resolve_by_account(self, account: str) -> AuthIdentity:
        if not self.api_url:
            raise DirectoryLookupUnavailableError("directory service is not configured")
        try:
            response = httpx.get(
                self.api_url,
                params={"account": account},
                timeout=self.timeout_seconds,
            )
        except httpx.RequestError as exc:
            raise DirectoryLookupUnavailableError("directory service request failed") from exc

        if response.status_code >= 500:
            raise DirectoryLookupUnavailableError("directory service unavailable")
        if response.status_code == 404:
            raise DirectoryLookupNotFoundError("target account not found")
        if response.status_code >= 400:
            raise DirectoryLookupUnavailableError("directory service unavailable")

        payload = response.json()
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict) and isinstance(payload.get("items"), list):
            items = payload.get("items") or []
        elif isinstance(payload, dict):
            items = [payload]
        else:
            items = []

        if not items:
            raise DirectoryLookupNotFoundError("target account not found")
        if len(items) > 1:
            raise DirectoryLookupNotUniqueError("target account is not unique")

        item = items[0]
        normalized = AuthIdentity(
            account=str(item.get("account", "")).strip(),
            name=str(item.get("name", "")).strip(),
            email=str(item.get("email", "")).strip().lower(),
            department=str(item.get("department", "")).strip(),
            sysid=str(item.get("sysid", "")).strip(),
        )
        if not all(
            [
                normalized.account,
                normalized.name,
                normalized.email,
                normalized.department,
                normalized.sysid,
            ]
        ):
            raise DirectoryLookupUnavailableError("directory service returned incomplete identity")
        return normalized

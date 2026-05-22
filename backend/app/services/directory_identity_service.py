from dataclasses import dataclass

from app.services.persnl_soap_service import PersnlSoapService, PersnlSoapUnavailableError
from db.repositories.types import AuthIdentity


class DirectoryLookupNotFoundError(RuntimeError):
    pass


class DirectoryLookupNotUniqueError(RuntimeError):
    pass


class DirectoryLookupUnavailableError(RuntimeError):
    pass


@dataclass(slots=True)
class DirectoryIdentityService:
    persnl: PersnlSoapService

    def __init__(self) -> None:
        self.persnl = PersnlSoapService()

    def is_configured(self) -> bool:
        return self.persnl.is_configured()

    def resolve_by_account(self, account: str) -> AuthIdentity:
        if not self.persnl.is_configured():
            raise DirectoryLookupUnavailableError("directory service is not configured")
        try:
            items = self.persnl.search_person_by_account(account)
        except PersnlSoapUnavailableError as exc:
            raise DirectoryLookupUnavailableError("directory service request failed") from exc

        if not items:
            raise DirectoryLookupNotFoundError("target account not found")
        if len(items) > 1:
            raise DirectoryLookupNotUniqueError("target account is not unique")

        item = items[0]
        normalized = self._to_auth_identity(item)
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

    def search_by_keyword(self, keyword: str, limit: int = 20) -> list[AuthIdentity]:
        if not self.persnl.is_configured():
            raise DirectoryLookupUnavailableError("directory service is not configured")
        try:
            raw_items = self.persnl.search_by_keyword(keyword, limit=limit * 2)
        except PersnlSoapUnavailableError as exc:
            raise DirectoryLookupUnavailableError("directory service request failed") from exc

        normalized_keyword = keyword.strip().lower()
        identities: list[AuthIdentity] = []
        for item in raw_items:
            try:
                identity = self._to_auth_identity(item)
            except (TypeError, ValueError):
                continue

            if not all([identity.account, identity.name, identity.email, identity.department, identity.sysid]):
                continue

            haystack_account = identity.account.lower()
            haystack_name = identity.name.lower()
            if normalized_keyword and normalized_keyword not in haystack_account and normalized_keyword not in haystack_name:
                continue
            identities.append(identity)
            if len(identities) >= limit:
                break

        return identities

    def _normalize_sysid(self, raw_sysid: object) -> int:
        text = str(raw_sysid).strip()
        if not text:
            raise ValueError("missing sysid")
        if not text.isdigit():
            raise ValueError("invalid sysid")
        return int(text)

    def _to_auth_identity(self, item: dict) -> AuthIdentity:
        return AuthIdentity(
            account=str(item.get("cn", "")).strip(),
            name=str(item.get("chName", "")).strip(),
            email=str(item.get("email", "")).strip().lower(),
            department=str(item.get("instCode", "")).strip(),
            sysid=self._normalize_sysid(item.get("sysId")),
        )

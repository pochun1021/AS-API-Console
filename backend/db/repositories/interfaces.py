from typing import Protocol

from db.models.applications import ApiKeyApplication
from db.models.api_keys import ApiKey
from db.models.users import User
from db.models.whitelist import ApiKeyWhitelist
from db.repositories.types import (
    ApiKeyCreateInput,
    ApiKeyDetail,
    ApiKeyListItem,
    ApplicationCreateInput,
    AuthIdentity,
    WhitelistCreateInput,
    WhitelistUpdateInput,
)


class UserRepository(Protocol):
    def get_by_id(self, user_id: str) -> User | None: ...

    def get_by_account(self, account: str) -> User | None: ...

    def get_by_email(self, email: str) -> User | None: ...

    def search(self, keyword: str, limit: int = 20) -> list[User]: ...

    def update_role(self, user_id: str, role: str) -> User | None: ...

    def upsert_from_auth(self, identity: AuthIdentity) -> User: ...


class WhitelistRepository(Protocol):
    def create(self, data: WhitelistCreateInput) -> ApiKeyWhitelist: ...

    def list(self, status: str | None = None, limit: int = 100, offset: int = 0) -> list[ApiKeyWhitelist]: ...

    def get_by_id(self, whitelist_id: str) -> ApiKeyWhitelist | None: ...

    def find_active_by_email(self, email: str) -> ApiKeyWhitelist | None: ...

    def update_status(self, whitelist_id: str, data: WhitelistUpdateInput) -> ApiKeyWhitelist | None: ...


class ApiKeyRepository(Protocol):
    def create_application(self, data: ApplicationCreateInput) -> ApiKeyApplication: ...

    def create_key(self, data: ApiKeyCreateInput) -> ApiKey: ...

    def list_keys(
        self,
        *,
        requester_role: str,
        requester_account: str,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[ApiKeyListItem]: ...

    def get_key_detail(self, key_id: str, requester_role: str, requester_account: str) -> ApiKeyDetail | None: ...

    def revoke_key(self, key_id: str, requester_role: str, requester_account: str) -> ApiKey | None: ...

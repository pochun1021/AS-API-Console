from datetime import date
from typing import Protocol

from db.models.applications import ApiKeyApplication
from db.models.api_keys import ApiKey
from db.models.users import User
from db.models.whitelist import ApiKeyWhitelist
from db.repositories.types import (
    ApiKeyAliasUpdateInput,
    ApiKeyCreateInput,
    ApiKeyDetail,
    ApiKeyListItem,
    ApiKeySecretMaterial,
    ApiKeyUserStatisticsItem,
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

    def update_status(self, user_id: str, status: str) -> User | None: ...
    
    def update_preferred_locale(self, user_id: str, preferred_locale: str | None) -> User | None: ...

    def upsert_from_auth(self, identity: AuthIdentity) -> User: ...


class WhitelistRepository(Protocol):
    def create(self, data: WhitelistCreateInput) -> ApiKeyWhitelist: ...

    def list(self, status: str | None = None, limit: int = 100, offset: int = 0) -> list[ApiKeyWhitelist]: ...

    def get_by_id(self, whitelist_id: str) -> ApiKeyWhitelist | None: ...

    def get_by_email(self, email: str) -> ApiKeyWhitelist | None: ...

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
    
    def get_key_secret_material(
        self, key_id: str, requester_role: str, requester_account: str
    ) -> ApiKeySecretMaterial | None: ...

    def revoke_key(self, key_id: str, requester_role: str, requester_account: str) -> ApiKey | None: ...

    def update_key_alias(
        self, key_id: str, requester_role: str, requester_account: str, data: ApiKeyAliasUpdateInput
    ) -> ApiKeyDetail | None: ...

    def list_user_statistics(
        self,
        *,
        scope: str,
        q: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        sort_by: str = "total_applications",
        sort_dir: str = "desc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ApiKeyUserStatisticsItem], int]: ...

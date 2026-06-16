from datetime import date, datetime
from typing import Protocol

from db.models.applications import ApiKeyApplication
from db.models.api_keys import ApiKey
from db.models.announcement import Announcement
from db.models.whitelist import ApiKeyWhitelist
from db.repositories.types import (
    AnnouncementCreateInput,
    AnnouncementListFilter,
    AnnouncementUpdateInput,
    ApiKeyAliasUpdateInput,
    ApiKeyCreateInput,
    ApiKeyDetail,
    ApiKeyListFilter,
    ApiKeyListItem,
    ApiKeySecretMaterial,
    ApiKeyUsageSeriesItem,
    ApiKeyUserStatisticsFilter,
    ApiKeyUserStatisticsItem,
    ApplicationCreateInput,
    AuthIdentity,
    WhitelistListFilter,
    WhitelistCreateInput,
    WhitelistUpdateInput,
)


class AnnouncementRepository(Protocol):
    def create(self, data: AnnouncementCreateInput) -> Announcement: ...

    def list(
        self,
        filters: AnnouncementListFilter,
        *,
        active_only: bool = False,
        now: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Announcement], int]: ...

    def get_by_id(self, announcement_id: str) -> Announcement | None: ...

    def update(self, announcement_id: str, data: AnnouncementUpdateInput) -> Announcement | None: ...

    def delete(self, announcement_id: str) -> Announcement | None: ...


class WhitelistRepository(Protocol):
    def create(self, data: WhitelistCreateInput) -> ApiKeyWhitelist: ...

    def list(
        self,
        filters: WhitelistListFilter,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ApiKeyWhitelist], int]: ...

    def get_by_id(self, whitelist_id: str) -> ApiKeyWhitelist | None: ...

    def get_by_sysid(self, sysid: int) -> ApiKeyWhitelist | None: ...

    def find_active_by_sysid(self, sysid: int) -> ApiKeyWhitelist | None: ...

    def update_status(self, whitelist_id: str, data: WhitelistUpdateInput) -> ApiKeyWhitelist | None: ...

    def delete(self, whitelist_id: str) -> ApiKeyWhitelist | None: ...


class ApiKeyRepository(Protocol):
    def create_application(self, data: ApplicationCreateInput) -> ApiKeyApplication: ...

    def create_key(self, data: ApiKeyCreateInput) -> ApiKey: ...

    def alias_exists(self, key_alias: str, *, exclude_key_id: str | None = None) -> bool: ...

    def list_keys(
        self,
        *,
        requester_role: str,
        requester_account: str,
        filters: ApiKeyListFilter,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ApiKeyListItem], int]: ...

    def get_key_detail(self, key_id: str, requester_role: str, requester_account: str) -> ApiKeyDetail | None: ...

    def list_usage_series(
        self,
        *,
        key_id: str,
        granularity: str,
        bucket_start_from: datetime,
        bucket_start_to: datetime,
    ) -> list[ApiKeyUsageSeriesItem]: ...

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
        filters: ApiKeyUserStatisticsFilter,
        sort_by: str = "total_applications",
        sort_dir: str = "desc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ApiKeyUserStatisticsItem], int]: ...

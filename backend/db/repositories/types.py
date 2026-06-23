from dataclasses import dataclass
from datetime import date, datetime


@dataclass(slots=True)
class AuthIdentity:
    account: str
    name: str
    email: str
    department: str
    sysid: int


@dataclass(slots=True)
class ApplicationCreateInput:
    identity: AuthIdentity
    is_proxy_submission: bool
    proxy_operator_account: str | None
    application_date: date
    duration_days: int
    original_duration_days: int
    purpose: str
    max_budget: str | None
    budget_duration: str | None
    tpm_limit: int | None
    rpm_limit: int | None
    max_parallel_requests: int | None
    issued_at: datetime
    expires_at: datetime


@dataclass(slots=True)
class ApiKeyCreateInput:
    application_id: str
    key_hash: str
    key_prefix: str
    masked_key: str
    key_alias: str | None
    key_ciphertext: str
    key_kek_version: str
    status: str = "active"


@dataclass(slots=True)
class ApiKeyListItem:
    id: str
    status: str
    masked_key: str
    key_alias: str | None
    created_at: datetime
    application_date: date
    duration_days: int
    original_duration_days: int
    owner_account: str
    owner_name: str
    expires_at: datetime
    expiration_notice_sent_at: datetime | None
    max_budget: str | None
    tpm_limit: int | None
    rpm_limit: int | None
    max_parallel_requests: int | None
    usage_spend: float | None
    usage_prompt_tokens: int | None
    usage_completion_tokens: int | None
    usage_total_tokens: int | None
    usage_budget_reset_at: datetime | None
    usage_synced_at: datetime | None


@dataclass(slots=True)
class ApiKeyUsageSeriesItem:
    bucket_start_utc: datetime
    bucket_end_utc: datetime
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    spend: float | None


@dataclass(slots=True)
class ApiKeyUsageTotal:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    key_count: int


@dataclass(slots=True)
class ApiKeyUsageBucketItem:
    api_key_id: str
    bucket_start_utc: datetime
    bucket_end_utc: datetime
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    spend: float | None


@dataclass(slots=True)
class ApiKeyListFilter:
    status: str | None = None
    owner_account: str | None = None
    owner_name: str | None = None
    key_alias: str | None = None
    application_date_from: date | None = None
    application_date_to: date | None = None
    expires_from: datetime | None = None
    expires_to: datetime | None = None
    sort_by: str = "created_at"
    sort_dir: str = "desc"


@dataclass(slots=True)
class ApiKeyDetail:
    id: str
    status: str
    masked_key: str
    key_alias: str | None
    owner_account: str
    owner_name: str
    purpose: str
    department: str
    application_date: date
    duration_days: int
    original_duration_days: int
    created_at: datetime
    expires_at: datetime
    expiration_notice_sent_at: datetime | None


@dataclass(slots=True)
class ApiKeyUserStatisticsItem:
    owner_account: str
    owner_name: str
    owner_email: str
    owner_department: str
    total_applications: int
    active_count: int
    revoked_count: int
    expired_count: int
    last_applied_at: date


@dataclass(slots=True)
class ApiKeyUserStatisticsFilter:
    q: str | None = None
    owner_account: str | None = None
    owner_name: str | None = None
    owner_email: str | None = None
    owner_department: str | None = None
    from_date: date | None = None
    to_date: date | None = None


@dataclass(slots=True)
class ApiKeySecretMaterial:
    id: str
    status: str
    owner_account: str
    key_ciphertext: str | None
    key_kek_version: str | None


@dataclass(slots=True)
class ApiKeyAliasUpdateInput:
    key_alias: str


@dataclass(slots=True)
class WhitelistCreateInput:
    id: str
    sysid: int
    account: str | None
    name: str | None
    email: str | None
    created_by: str
    note: str | None = None


@dataclass(slots=True)
class WhitelistUpdateInput:
    status: str
    updated_by: str
    note: str | None = None


@dataclass(slots=True)
class WhitelistListFilter:
    status: str | None = None
    sysid: int | None = None
    account: str | None = None
    name: str | None = None
    email: str | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    updated_from: datetime | None = None
    updated_to: datetime | None = None
    sort_by: str = "created_at"
    sort_dir: str = "desc"


@dataclass(slots=True)
class AnnouncementCreateInput:
    id: str
    title: str
    body: str
    status: str
    publish_from: datetime | None
    publish_to: datetime | None
    created_by: str


@dataclass(slots=True)
class AnnouncementUpdateInput:
    title: str
    body: str
    status: str
    publish_from: datetime | None
    publish_to: datetime | None
    updated_by: str


@dataclass(slots=True)
class AnnouncementListFilter:
    title: str | None = None
    status: str | None = None
    publish_from_from: datetime | None = None
    publish_from_to: datetime | None = None
    publish_to_from: datetime | None = None
    publish_to_to: datetime | None = None
    updated_from: datetime | None = None
    updated_to: datetime | None = None
    sort_by: str = "updated_at"
    sort_dir: str = "desc"


@dataclass(slots=True)
class AdminListFilter:
    status: str | None = None
    sysid: int | None = None
    account: str | None = None
    name: str | None = None
    email: str | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    updated_from: datetime | None = None
    updated_to: datetime | None = None
    sort_by: str = "created_at"
    sort_dir: str = "desc"

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
    user_id: int
    identity: AuthIdentity
    operator_identity: AuthIdentity
    is_proxy_submission: bool
    application_date: date
    duration_months: int
    purpose: str
    limit_strategy: str
    max_budget: str | None
    budget_duration: str | None
    tpm_limit: int | None
    rpm_limit: int | None
    issuance_status: str
    pending_issued_at: datetime | None
    issued_at: datetime
    expires_at: datetime


@dataclass(slots=True)
class ApiKeyCreateInput:
    application_id: str
    key_hash: str
    masked_key: str
    key_ciphertext: str
    key_kek_version: str
    status: str = "active"


@dataclass(slots=True)
class ApiKeyListItem:
    id: str
    status: str
    masked_key: str
    key_alias: str | None
    application_date: date
    duration_months: int
    owner_account: str
    owner_name: str
    expires_at: datetime
    expiration_notice_sent_at: datetime | None


@dataclass(slots=True)
class ApiKeyListFilter:
    status: str | None = None
    owner_account: str | None = None
    from_date: date | None = None
    to_date: date | None = None


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
    duration_months: int
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

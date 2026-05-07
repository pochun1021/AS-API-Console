from dataclasses import dataclass
from datetime import date, datetime


@dataclass(slots=True)
class AuthIdentity:
    account: str
    name: str
    email: str
    department: str
    sysid: str


@dataclass(slots=True)
class ApplicationCreateInput:
    user_id: str
    identity: AuthIdentity
    application_date: date
    duration_months: int
    purpose: str
    issued_at: datetime
    expires_at: datetime


@dataclass(slots=True)
class ApiKeyCreateInput:
    application_id: str
    key_hash: str
    status: str = "active"


@dataclass(slots=True)
class ApiKeyListItem:
    id: str
    status: str
    key_prefix: str
    application_date: date
    duration_months: int
    owner_account: str
    owner_name: str
    expires_at: datetime


@dataclass(slots=True)
class ApiKeyDetail:
    id: str
    status: str
    key_prefix: str
    owner_account: str
    owner_name: str
    purpose: str
    department: str
    application_date: date
    duration_months: int
    created_at: datetime
    expires_at: datetime


@dataclass(slots=True)
class ApiKeyUserStatisticsItem:
    owner_account: str
    owner_name: str
    owner_email: str
    total_applications: int
    active_count: int
    revoked_count: int
    expired_count: int
    last_applied_at: date


@dataclass(slots=True)
class WhitelistCreateInput:
    id: str
    email: str
    created_by: str
    note: str | None = None


@dataclass(slots=True)
class WhitelistUpdateInput:
    status: str
    updated_by: str
    note: str | None = None

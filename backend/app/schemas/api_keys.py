from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ApplicationCreateRequest(BaseModel):
    application_date: date
    duration_months: int = Field(..., description="allowed: 1, 6, 12")
    purpose: str


class ApplicationSummary(BaseModel):
    id: str
    account: str
    status: str
    issued_at: datetime
    expires_at: datetime


class ApplicationCreateResponse(BaseModel):
    application: ApplicationSummary
    issuance_status: Literal["issued", "pending"]
    api_key_plaintext: str | None = None
    pending_reason: str | None = None


class PendingApplicationItemResponse(BaseModel):
    id: str
    account: str
    name: str
    email: str
    department: str
    purpose: str
    application_date: date
    duration_months: int
    selected_issuance_mode: Literal["budget", "rate_limit"] | None = None
    created_at: datetime


class PendingApplicationListResponse(BaseModel):
    items: list[PendingApplicationItemResponse]
    total: int


class PendingApplicationModeUpdateRequest(BaseModel):
    mode: Literal["budget", "rate_limit"]


class PendingApplicationModeUpdateResponse(BaseModel):
    id: str
    selected_issuance_mode: Literal["budget", "rate_limit"]
    issuance_status: Literal["pending", "issued"]


class PendingApplicationIssueResponse(BaseModel):
    application: ApplicationSummary
    issuance_status: Literal["pending", "issued"]
    api_key_plaintext: str | None = None
    pending_reason: str | None = None
    email_warning: str | None = None


class ApiKeyListItemResponse(BaseModel):
    id: str
    status: str
    masked_key: str
    key_alias: str
    application_date: date
    duration_months: int
    owner_account: str
    owner_name: str
    expires_at: datetime


class ApiKeyListResponse(BaseModel):
    items: list[ApiKeyListItemResponse]
    page: int
    page_size: int
    total: int


class ApiKeyDetailResponse(BaseModel):
    id: str
    status: str
    masked_key: str
    key_alias: str
    owner_account: str
    owner_name: str
    purpose: str
    department: str
    application_date: date
    duration_months: int
    created_at: datetime
    expires_at: datetime


class RevokeResponse(BaseModel):
    id: str
    status: str


class ApiKeyRevealResponse(BaseModel):
    id: str
    api_key_plaintext: str
    key_kek_version: str


class ApiKeyAliasUpdateRequest(BaseModel):
    key_alias: str


class ApiKeyUserStatisticsItemResponse(BaseModel):
    owner_account: str
    owner_name: str
    owner_email: str
    owner_department: str
    total_applications: int
    active_count: int
    revoked_count: int
    expired_count: int
    last_applied_at: date


class ApiKeyUserStatisticsResponse(BaseModel):
    items: list[ApiKeyUserStatisticsItemResponse]
    page: int
    page_size: int
    total: int


class LimitStrategyConfigResponse(BaseModel):
    budget_max_budget: str
    budget_duration: str
    rate_limit_tpm: int
    rate_limit_rpm: int


class LimitStrategyConfigUpdateRequest(BaseModel):
    budget_max_budget: str
    budget_duration: str
    rate_limit_tpm: int
    rate_limit_rpm: int

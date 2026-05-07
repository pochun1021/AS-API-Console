from datetime import date, datetime

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
    api_key_plaintext: str
    api_key_prefix: str


class ApiKeyListItemResponse(BaseModel):
    id: str
    status: str
    masked_key: str
    key_prefix: str
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
    key_prefix: str
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


class ApiKeyUserStatisticsItemResponse(BaseModel):
    owner_account: str
    owner_name: str
    owner_email: str
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

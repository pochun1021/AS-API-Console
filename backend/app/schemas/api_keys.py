from datetime import date, datetime

from pydantic import BaseModel, Field, field_serializer

from app.schemas.datetime_serializers import serialize_utc_datetime


class ApplicationCreateRequest(BaseModel):
    application_date: date
    duration_months: int = Field(..., description="allowed: 1, 6, 12")
    purpose: str
    target_identity: "ApplicationTargetIdentityRequest | None" = None


class ApplicationTargetIdentityRequest(BaseModel):
    account: str


class ApplicationSummary(BaseModel):
    id: str
    account: str
    status: str
    issued_at: datetime
    expires_at: datetime

    @field_serializer("issued_at", "expires_at")
    def serialize_datetimes(self, value: datetime) -> str:
        return serialize_utc_datetime(value)


class ApplicationCreateResponse(BaseModel):
    application: ApplicationSummary
    api_key_plaintext: str | None = None


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
    expiration_notice_sent_at: datetime | None = None
    extend_eligible: bool = False

    @field_serializer("expires_at", "expiration_notice_sent_at")
    def serialize_datetimes(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return serialize_utc_datetime(value)


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
    expiration_notice_sent_at: datetime | None = None
    extend_eligible: bool = False

    @field_serializer("created_at", "expires_at", "expiration_notice_sent_at")
    def serialize_datetimes(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return serialize_utc_datetime(value)


class RevokeResponse(BaseModel):
    id: str
    status: str


class RenewResponse(BaseModel):
    id: str
    status: str
    expires_at: datetime
    renewed_from_key_id: str
    api_key_plaintext: str | None = None
    email_warning: str | None = None

    @field_serializer("expires_at")
    def serialize_datetimes(self, value: datetime) -> str:
        return serialize_utc_datetime(value)


class ExtendRequest(BaseModel):
    duration_months: int = Field(..., description="allowed: 1, 6, 12")


class ExtendResponse(BaseModel):
    id: str
    status: str
    expires_at: datetime

    @field_serializer("expires_at")
    def serialize_datetimes(self, value: datetime) -> str:
        return serialize_utc_datetime(value)


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

from datetime import datetime

from pydantic import BaseModel, field_serializer

from app.schemas.datetime_serializers import serialize_utc_datetime


class UserListItemResponse(BaseModel):
    id: str
    sysid: int
    account: str
    name: str
    email: str
    department: str
    role: str
    status: str


class UserListResponse(BaseModel):
    items: list[UserListItemResponse]
    total: int


class AdminListItemResponse(UserListItemResponse):
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_datetimes(self, value: datetime) -> str:
        return serialize_utc_datetime(value)


class AdminListResponse(BaseModel):
    items: list[AdminListItemResponse]
    page: int
    page_size: int
    total: int


class UserRoleMutationResponse(BaseModel):
    id: int
    role: str
    status: str


class AdminCreateRequest(BaseModel):
    account: str
    name: str
    email: str
    department: str


class UserLocalePreferenceResponse(BaseModel):
    preferred_locale: str | None


class UserLocalePreferenceUpdateRequest(BaseModel):
    preferred_locale: str


class CurrentUserResponse(BaseModel):
    account: str
    name: str
    email: str
    department: str
    sysid: int
    role: str
    csrf_token: str

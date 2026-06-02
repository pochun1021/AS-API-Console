from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_serializer

from app.schemas.datetime_serializers import serialize_utc_datetime


class AuthAuditLogItemResponse(BaseModel):
    id: str
    created_at: datetime
    provider: str
    result: Literal["success", "failure"]
    account: str | None
    sysid: int | None
    role: str | None
    error_code: str | None
    request_id: str

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return serialize_utc_datetime(value)


class AuthAuditLogListResponse(BaseModel):
    items: list[AuthAuditLogItemResponse]
    page: int
    page_size: int
    total: int

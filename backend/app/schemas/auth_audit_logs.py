from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, field_serializer


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
        normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return normalized.astimezone(UTC).isoformat().replace("+00:00", "Z")


class AuthAuditLogListResponse(BaseModel):
    items: list[AuthAuditLogItemResponse]
    page: int
    page_size: int
    total: int

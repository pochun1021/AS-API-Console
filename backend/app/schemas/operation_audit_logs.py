from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_serializer

from app.schemas.datetime_serializers import serialize_utc_datetime


class OperationAuditLogItemResponse(BaseModel):
    id: str
    created_at: datetime
    event_type: str
    action: str
    result: Literal["success", "failure"]
    actor_account: str | None
    target_type: str
    target_id: str | None
    error_code: str | None

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return serialize_utc_datetime(value)


class OperationAuditLogListResponse(BaseModel):
    items: list[OperationAuditLogItemResponse]
    page: int
    page_size: int
    total: int

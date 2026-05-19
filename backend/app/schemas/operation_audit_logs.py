from datetime import datetime
from typing import Literal

from pydantic import BaseModel


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


class OperationAuditLogListResponse(BaseModel):
    items: list[OperationAuditLogItemResponse]
    page: int
    page_size: int
    total: int

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


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


class AuthAuditLogListResponse(BaseModel):
    items: list[AuthAuditLogItemResponse]
    page: int
    page_size: int
    total: int

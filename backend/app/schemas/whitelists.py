from datetime import datetime

from pydantic import BaseModel


class WhitelistCreateRequest(BaseModel):
    sysid: int
    note: str | None = None


class WhitelistItemResponse(BaseModel):
    id: str
    sysid: int
    email: str | None
    status: str
    note: str | None
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime


class WhitelistListResponse(BaseModel):
    items: list[WhitelistItemResponse]
    page: int
    page_size: int
    total: int


class WhitelistUpdateRequest(BaseModel):
    status: str
    note: str | None = None

from datetime import datetime

from pydantic import BaseModel


class WhitelistCreateRequest(BaseModel):
    sysid: int
    account: str
    name: str
    email: str
    note: str | None = None


class WhitelistItemResponse(BaseModel):
    id: str
    sysid: int
    account: str | None
    name: str | None
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

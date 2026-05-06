from datetime import datetime

from pydantic import BaseModel, EmailStr


class WhitelistCreateRequest(BaseModel):
    email: EmailStr
    note: str | None = None


class WhitelistItemResponse(BaseModel):
    id: str
    email: str
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

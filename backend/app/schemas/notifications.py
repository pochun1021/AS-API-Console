from datetime import datetime

from pydantic import BaseModel


class NotificationMetadata(BaseModel):
    application_id: str | None = None
    key_id: str | None = None


class NotificationItemResponse(BaseModel):
    id: str
    type: str
    title: str
    message: str
    is_read: bool
    created_at: datetime
    read_at: datetime | None = None
    metadata: NotificationMetadata | None = None


class NotificationListResponse(BaseModel):
    items: list[NotificationItemResponse]
    page: int
    page_size: int
    total: int


class NotificationReadResponse(BaseModel):
    id: str
    is_read: bool
    read_at: datetime | None = None


class NotificationReadAllResponse(BaseModel):
    updated: int

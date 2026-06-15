from datetime import datetime

from pydantic import BaseModel, field_serializer

from app.schemas.datetime_serializers import serialize_utc_datetime


class AnnouncementItemResponse(BaseModel):
    id: str
    title: str
    body: str
    status: str
    publish_from: datetime | None
    publish_to: datetime | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("publish_from", "publish_to", "created_at", "updated_at")
    def serialize_datetimes(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return serialize_utc_datetime(value)


class AnnouncementListResponse(BaseModel):
    items: list[AnnouncementItemResponse]
    page: int
    page_size: int
    total: int


class AnnouncementMutationRequest(BaseModel):
    title: str
    body: str
    status: str
    publish_from: datetime | None = None
    publish_to: datetime | None = None


class AnnouncementCreateRequest(AnnouncementMutationRequest):
    pass


class AnnouncementUpdateRequest(AnnouncementMutationRequest):
    pass

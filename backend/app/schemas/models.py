from datetime import datetime

from pydantic import BaseModel, field_serializer

from app.schemas.datetime_serializers import serialize_utc_datetime


class ModelItemResponse(BaseModel):
    id: str
    label: str


class ModelListResponse(BaseModel):
    items: list[ModelItemResponse]
    total: int
    fetched_at: datetime

    @field_serializer("fetched_at")
    def serialize_fetched_at(self, value: datetime) -> str:
        return serialize_utc_datetime(value)

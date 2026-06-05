from datetime import datetime

from pydantic import BaseModel, field_serializer, model_validator

from app.core.input_validation import validate_safe_persisted_text

from app.schemas.datetime_serializers import serialize_utc_datetime


class WhitelistCreateRequest(BaseModel):
    sysid: int
    account: str
    name: str
    email: str
    note: str | None = None

    @model_validator(mode="after")
    def validate_inputs(self) -> "WhitelistCreateRequest":
        self.note = validate_safe_persisted_text(
            field_name="note",
            value=self.note,
            allow_empty=True,
            restrict_special_chars=True,
            allow_spaces=True,
        )
        return self


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

    @field_serializer("created_at", "updated_at")
    def serialize_datetimes(self, value: datetime) -> str:
        return serialize_utc_datetime(value)


class WhitelistListResponse(BaseModel):
    items: list[WhitelistItemResponse]
    page: int
    page_size: int
    total: int


class WhitelistUpdateRequest(BaseModel):
    status: str
    note: str | None = None

    @model_validator(mode="after")
    def validate_inputs(self) -> "WhitelistUpdateRequest":
        self.note = validate_safe_persisted_text(
            field_name="note",
            value=self.note,
            allow_empty=True,
            restrict_special_chars=True,
            allow_spaces=True,
        )
        return self

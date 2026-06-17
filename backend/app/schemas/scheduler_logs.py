from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, field_serializer


class SchedulerLogItemResponse(BaseModel):
    id: str
    job: Literal["sync_expired_api_keys", "sync_api_key_usage", "send_expiration_reminders"]
    log_date: date
    source_file: str
    timestamp: datetime
    level: Literal["INFO", "WARNING", "ERROR", "CRITICAL"]
    message: str
    raw_line: str

    @field_serializer("log_date")
    def serialize_log_date(self, value: date) -> str:
        return value.isoformat()

    @field_serializer("timestamp")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.isoformat(timespec="seconds")


class AvailableSchedulerLogFileResponse(BaseModel):
    log_date: date
    source_file: str

    @field_serializer("log_date")
    def serialize_log_date(self, value: date) -> str:
        return value.isoformat()


class SchedulerLogListResponse(BaseModel):
    available_files: list[AvailableSchedulerLogFileResponse]
    items: list[SchedulerLogItemResponse]
    page: int
    page_size: int
    total: int

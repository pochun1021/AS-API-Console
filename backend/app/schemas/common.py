from datetime import datetime

from pydantic import BaseModel


class ErrorDetailResponse(BaseModel):
    code: str
    message: str
    details: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetailResponse
    retry_after_seconds: int | None = None
    next_allowed_at: datetime | None = None

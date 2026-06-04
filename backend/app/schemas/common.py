from pydantic import BaseModel


class ErrorDetailResponse(BaseModel):
    code: str
    message: str
    details: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetailResponse

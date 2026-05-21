from pydantic import BaseModel


class ErrorDetailResponse(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetailResponse

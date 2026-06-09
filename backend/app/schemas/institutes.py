from datetime import datetime

from pydantic import BaseModel


class InstituteItemResponse(BaseModel):
    inst_code: str
    inst_name: str
    abb_inst_name: str | None
    einst_name: str | None
    division: str | None


class InstituteListResponse(BaseModel):
    items: list[InstituteItemResponse]
    total: int


class InstituteSyncResponse(BaseModel):
    fetched_count: int
    inserted_count: int
    updated_count: int
    unchanged_count: int
    deactivated_count: int


class InstituteSyncStatusResponse(BaseModel):
    status: str
    retry_after_seconds: int
    next_allowed_at: datetime | None

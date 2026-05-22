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

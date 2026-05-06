from pydantic import BaseModel


class UserListItemResponse(BaseModel):
    id: str
    sysid: str
    account: str
    name: str
    email: str
    role: str
    status: str


class UserListResponse(BaseModel):
    items: list[UserListItemResponse]
    total: int


class UserRoleMutationResponse(BaseModel):
    id: str
    role: str

from pydantic import BaseModel


class UserListItemResponse(BaseModel):
    id: str
    sysid: int
    account: str
    name: str
    email: str
    department: str
    role: str
    status: str


class UserListResponse(BaseModel):
    items: list[UserListItemResponse]
    total: int


class UserRoleMutationResponse(BaseModel):
    id: int
    role: str
    status: str


class AdminCreateRequest(BaseModel):
    account: str
    name: str
    email: str
    department: str


class UserLocalePreferenceResponse(BaseModel):
    preferred_locale: str | None


class UserLocalePreferenceUpdateRequest(BaseModel):
    preferred_locale: str


class CurrentUserResponse(BaseModel):
    account: str
    name: str
    email: str
    department: str
    sysid: int
    role: str
    csrf_token: str

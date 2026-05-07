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
    status: str


class UserLocalePreferenceResponse(BaseModel):
    preferred_locale: str | None


class UserLocalePreferenceUpdateRequest(BaseModel):
    preferred_locale: str

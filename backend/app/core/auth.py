from dataclasses import dataclass

from fastapi import Header

from app.core.errors import ApiError


@dataclass(slots=True)
class CurrentUser:
    account: str
    name: str
    email: str
    department: str
    sysid: str
    role: str


def get_current_user(
    x_account: str | None = Header(default=None),
    x_name: str | None = Header(default=None),
    x_email: str | None = Header(default=None),
    x_department: str | None = Header(default=None),
    x_sysid: str | None = Header(default=None),
    x_role: str | None = Header(default="user"),
) -> CurrentUser:
    missing = [
        key
        for key, value in {
            "x-account": x_account,
            "x-name": x_name,
            "x-email": x_email,
            "x-department": x_department,
            "x-sysid": x_sysid,
        }.items()
        if not value
    ]
    if missing:
        raise ApiError("VALIDATION_ERROR", f"missing auth headers: {', '.join(missing)}", 422)

    role = (x_role or "user").lower()
    if role not in {"user", "admin"}:
        raise ApiError("VALIDATION_ERROR", "invalid role", 422)

    return CurrentUser(
        account=x_account or "",
        name=x_name or "",
        email=(x_email or "").lower(),
        department=x_department or "",
        sysid=x_sysid or "",
        role=role,
    )

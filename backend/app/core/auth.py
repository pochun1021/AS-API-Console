from dataclasses import dataclass

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from db.repositories import SQLAlchemyUserRepository
from db.session import get_db


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
    db: Session = Depends(get_db),
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

    user = SQLAlchemyUserRepository(db).get_by_account(x_account or "")
    if user is not None and user.status == "inactive":
        raise ApiError("FORBIDDEN", "user is disabled", 403)

    return CurrentUser(
        account=x_account or "",
        name=x_name or "",
        email=(x_email or "").lower(),
        department=x_department or "",
        sysid=x_sysid or "",
        role=role,
    )

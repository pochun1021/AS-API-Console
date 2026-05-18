from dataclasses import dataclass

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from db.repositories import SQLAlchemyAdminRepository
from db.repositories.types import AuthIdentity
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
    request: Request,
    x_account: str | None = Header(default=None),
    x_name: str | None = Header(default=None),
    x_email: str | None = Header(default=None),
    x_department: str | None = Header(default=None),
    x_sysid: str | None = Header(default=None),
    x_role: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> CurrentUser:
    session_auth = request.session.get("auth_context") if hasattr(request, "session") else None
    if isinstance(session_auth, dict):
        x_account = x_account or session_auth.get("account")
        x_name = x_name or session_auth.get("name")
        x_email = x_email or session_auth.get("email")
        x_department = x_department or session_auth.get("department")
        x_sysid = x_sysid or session_auth.get("sysid")
        x_role = x_role or session_auth.get("role")

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

    if role == "admin":
        repo = SQLAlchemyAdminRepository(db)
        admin = repo.get_by_account(x_account or "")
        if admin is None:
            repo.upsert_from_auth(
                AuthIdentity(
                    account=x_account or "",
                    name=x_name or "",
                    email=x_email or "",
                    department=x_department or "",
                    sysid=x_sysid or "",
                ),
                created_by=x_account or "system",
            )
            db.commit()
            admin = repo.get_by_account(x_account or "")
        if admin is None or admin.status != "active":
            raise ApiError("FORBIDDEN", "admin is disabled", 403)

    return CurrentUser(
        account=x_account or "",
        name=x_name or "",
        email=(x_email or "").lower(),
        department=x_department or "",
        sysid=x_sysid or "",
        role=role,
    )

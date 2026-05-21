from dataclasses import dataclass

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
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
    sysid: int
    role: str


def _resolve_admin_role(
    *,
    db: Session,
    account: str,
    name: str,
    email: str,
    department: str,
    sysid: int,
    requested_role: str,
    allow_header_auth: bool,
) -> str:
    repo = SQLAlchemyAdminRepository(db)
    admin = repo.get_by_account(account or "")
    if requested_role == "admin" and allow_header_auth:
        if admin is None:
            repo.upsert_from_auth(
                AuthIdentity(
                    account=account,
                    name=name,
                    email=email,
                    department=department,
                    sysid=sysid,
                ),
                created_by=account or "system",
            )
            db.commit()
            admin = repo.get_by_account(account or "")
        if admin is None or admin.status != "active":
            raise ApiError("FORBIDDEN", "admin is disabled", 403)
        return "admin"
    if admin is not None and admin.status == "active":
        return "admin"
    return "user"


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
    settings = get_settings()
    session_auth = request.session.get("auth_context") if hasattr(request, "session") else None
    used_header_auth = False
    if isinstance(session_auth, dict):
        x_account = session_auth.get("account")
        x_name = session_auth.get("name")
        x_email = session_auth.get("email")
        x_department = session_auth.get("department")
        x_sysid = session_auth.get("sysid")
        x_role = session_auth.get("role")
    elif settings.header_auth_enabled:
        used_header_auth = True
    else:
        raise ApiError("UNAUTHORIZED", "login required", 401)

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

    try:
        normalized_sysid = int(x_sysid or "")
    except ValueError as exc:
        raise ApiError("VALIDATION_ERROR", "x-sysid must be numeric", 422) from exc
    if normalized_sysid <= 0:
        raise ApiError("VALIDATION_ERROR", "x-sysid must be positive integer", 422)

    resolved_role = _resolve_admin_role(
        db=db,
        account=x_account or "",
        name=x_name or "",
        email=(x_email or "").lower(),
        department=x_department or "",
        sysid=normalized_sysid,
        requested_role=role,
        allow_header_auth=used_header_auth,
    )

    return CurrentUser(
        account=x_account or "",
        name=x_name or "",
        email=(x_email or "").lower(),
        department=x_department or "",
        sysid=normalized_sysid,
        role=resolved_role,
    )

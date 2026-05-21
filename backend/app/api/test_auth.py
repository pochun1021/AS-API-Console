from pydantic import BaseModel, EmailStr
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import ensure_csrf_token
from db.repositories import SQLAlchemyAdminRepository
from db.repositories.types import AuthIdentity
from db.session import get_db

router = APIRouter()


class TestSessionLoginRequest(BaseModel):
    account: str
    name: str
    email: EmailStr
    department: str
    sysid: int
    role: str = "user"


@router.post("/test/session-login", include_in_schema=False)
def test_session_login(
    payload: TestSessionLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str | int]:
    role = payload.role.lower()
    if role not in {"user", "admin"}:
        raise ApiError("VALIDATION_ERROR", "invalid role", 422)

    request.session["auth_context"] = {
        "account": payload.account,
        "name": payload.name,
        "email": payload.email.lower(),
        "department": payload.department,
        "sysid": payload.sysid,
        "role": role,
    }
    csrf_token = ensure_csrf_token(request)

    if role == "admin":
        repo = SQLAlchemyAdminRepository(db)
        repo.upsert_from_auth(
            AuthIdentity(
                account=payload.account,
                name=payload.name,
                email=payload.email.lower(),
                department=payload.department,
                sysid=payload.sysid,
            ),
            created_by="test-session-login",
        )
        db.commit()

    return {
        "account": payload.account,
        "name": payload.name,
        "email": payload.email.lower(),
        "department": payload.department,
        "sysid": payload.sysid,
        "role": role,
        "csrf_token": csrf_token,
    }

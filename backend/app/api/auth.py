from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApiError
from app.services.auth_audit_service import AuthAuditService
from app.services.oauth_service import OAuthService
from db.session import get_db

router = APIRouter()


@router.get("/login")
def login(request: Request) -> RedirectResponse:
    request_id = str(uuid4())
    request.session["oauth_request_id"] = request_id
    service = OAuthService()
    return RedirectResponse(service.build_login_url(request_id), status_code=302)


@router.get("/auth/callback")
def oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    settings = get_settings()
    provider = settings.oauth_provider
    expected_state = request.session.get("oauth_request_id")
    request_id = state or expected_state or str(uuid4())
    audit = AuthAuditService(db)

    if not code:
        audit.log(provider=provider, request_id=request_id, result="failure", error_code="OAUTH_CODE_MISSING")
        raise ApiError("OAUTH_CODE_MISSING", "oauth callback code missing", 422)
    if state and expected_state and state != expected_state:
        audit.log(provider=provider, request_id=request_id, result="failure", error_code="OAUTH_STATE_MISMATCH")
        raise ApiError("OAUTH_STATE_MISMATCH", "oauth state mismatch", 401)

    try:
        oauth = OAuthService()
        token = oauth.exchange_code_for_token(code)
        identity = oauth.fetch_identity(token)
    except ApiError as exc:
        audit.log(provider=provider, request_id=request_id, result="failure", error_code=exc.code)
        raise

    request.session["auth_context"] = {
        "account": identity.account,
        "name": identity.name,
        "email": identity.email.lower(),
        "department": identity.department,
        "sysid": identity.sysid,
        "role": "user",
    }
    request.session.pop("oauth_request_id", None)
    audit.log(
        provider=provider,
        request_id=request_id,
        result="success",
        account=identity.account,
        name=identity.name,
        email=identity.email,
        department=identity.department,
        sysid=identity.sysid,
        role="user",
    )
    return RedirectResponse("/", status_code=302)


@router.post("/logout")
def logout(request: Request) -> dict[str, str]:
    request.session.pop("auth_context", None)
    request.session.pop("oauth_request_id", None)
    return {"status": "ok"}

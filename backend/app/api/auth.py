from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.security import csrf_protected, enforce_rate_limit, ensure_csrf_token
from app.schemas.common import ErrorResponse
from app.services.auth_audit_service import AuthAuditService
from app.services.oauth_service import OAuthService
from db.repositories.types import AuthIdentity
from db.repositories import SQLAlchemyAdminRepository, SQLAlchemyWhitelistRepository
from db.session import get_db

router = APIRouter()
settings = get_settings()


def _parse_allowed_tcodes(raw: str) -> set[str]:
    return {code.strip().upper() for code in raw.split(",") if code.strip()}


@router.get(
    "/login",
    status_code=302,
    response_class=RedirectResponse,
    dependencies=[enforce_rate_limit("login", settings.login_rate_limit)],
    responses={
        302: {"description": "Redirect to OAuth provider"},
        500: {"model": ErrorResponse, "description": "OAuth configuration is invalid or incomplete"},
    },
)
def login(
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    current_settings = get_settings()
    env = current_settings.app_env.lower()
    if env in {"dev", "test"}:
        dev_role = (current_settings.dev_login_role or "user").strip().lower()
        if dev_role not in {"user", "admin"}:
            raise ApiError("INTERNAL_ERROR", "invalid DEV_LOGIN_ROLE: must be user or admin", 500)
        required = {
            "DEV_LOGIN_ACCOUNT": current_settings.dev_login_account,
            "DEV_LOGIN_NAME": current_settings.dev_login_name,
            "DEV_LOGIN_EMAIL": current_settings.dev_login_email,
            "DEV_LOGIN_DEPARTMENT": current_settings.dev_login_department,
            "DEV_LOGIN_SYSID": current_settings.dev_login_sysid,
        }
        missing = [key for key, value in required.items() if value in {None, ""}]
        if missing:
            raise ApiError("INTERNAL_ERROR", f"missing dev login config: {', '.join(missing)}", 500)
        assert current_settings.dev_login_sysid is not None
        request.session["auth_context"] = {
            "account": current_settings.dev_login_account,
            "name": current_settings.dev_login_name,
            "email": current_settings.dev_login_email.lower(),
            "department": current_settings.dev_login_department,
            "sysid": current_settings.dev_login_sysid,
            "role": dev_role,
        }
        if dev_role == "admin":
            SQLAlchemyAdminRepository(db).upsert_from_auth(
                AuthIdentity(
                    account=current_settings.dev_login_account or "",
                    name=current_settings.dev_login_name or "",
                    email=(current_settings.dev_login_email or "").lower(),
                    department=current_settings.dev_login_department or "",
                    sysid=current_settings.dev_login_sysid,
                ),
                created_by=current_settings.dev_login_account or "dev-login",
            )
            db.commit()
        request.session.pop("oauth_request_id", None)
        ensure_csrf_token(request)
        return RedirectResponse("/main/", status_code=302)

    request_id = str(uuid4())
    request.session["oauth_request_id"] = request_id
    ensure_csrf_token(request)
    service = OAuthService()
    return RedirectResponse(service.build_login_url(request_id), status_code=302)


@router.get(
    "/auth/callback",
    status_code=302,
    response_class=RedirectResponse,
    dependencies=[enforce_rate_limit("oauth_callback", settings.login_rate_limit)],
    responses={
        302: {"description": "OAuth callback success and redirect to frontend"},
        401: {"model": ErrorResponse, "description": "OAuth state is missing or mismatched"},
        403: {"model": ErrorResponse, "description": "User is not eligible to login"},
        422: {"model": ErrorResponse, "description": "OAuth callback payload is invalid"},
    },
)
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
    if not expected_state:
        audit.log(provider=provider, request_id=request_id, result="failure", error_code="OAUTH_STATE_MISSING")
        raise ApiError("OAUTH_STATE_MISSING", "oauth state missing", 401)
    if not state or state != expected_state:
        request.session.pop("oauth_request_id", None)
        audit.log(provider=provider, request_id=request_id, result="failure", error_code="OAUTH_STATE_MISMATCH")
        raise ApiError("OAUTH_STATE_MISMATCH", "oauth state mismatch", 401)

    try:
        oauth = OAuthService()
        token = oauth.exchange_code_for_token(code)
        identity = oauth.fetch_identity(token)
    except ApiError as exc:
        audit.log(provider=provider, request_id=request_id, result="failure", error_code=exc.code)
        raise

    whitelist_repo = SQLAlchemyWhitelistRepository(db)
    admin_repo = SQLAlchemyAdminRepository(db)
    allowed_tcodes = _parse_allowed_tcodes(settings.login_allowed_title_codes)
    allow_by_tcode = identity.tcode.strip().upper() in allowed_tcodes
    allow_by_whitelist = whitelist_repo.find_active_by_sysid(identity.sysid) is not None
    admin = admin_repo.get_by_id(identity.sysid)
    allow_by_admin = admin is not None and admin.status == "active"
    if not (allow_by_tcode or allow_by_whitelist or allow_by_admin):
        audit.log(provider=provider, request_id=request_id, result="failure", error_code="LOGIN_NOT_ELIGIBLE")
        raise ApiError("LOGIN_NOT_ELIGIBLE", "user is not eligible to login", 403)

    request.session["auth_context"] = {
        "account": identity.account,
        "name": identity.name,
        "email": identity.email.lower(),
        "department": identity.department,
        "sysid": identity.sysid,
        "role": "user",
    }
    request.session.pop("oauth_request_id", None)
    ensure_csrf_token(request)
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
    return RedirectResponse("/main/", status_code=302)


@router.post("/logout", dependencies=[Depends(csrf_protected), enforce_rate_limit("logout", settings.login_rate_limit)])
def logout(request: Request) -> dict[str, str]:
    request.session.pop("auth_context", None)
    request.session.pop("oauth_request_id", None)
    request.session.pop("csrf_token", None)
    return {"status": "ok"}

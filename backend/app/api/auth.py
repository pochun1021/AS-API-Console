from uuid import uuid4
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.security import csrf_protected, enforce_rate_limit, ensure_csrf_token
from app.schemas.common import ErrorResponse
from app.services.auth_audit_service import AuthAuditService
from app.services.login_eligibility_service import LoginEligibilityService
from app.services.oauth_service import OAuthService
from app.services.login_qualification_gate import GateStatus, LoginQualificationGate
from app.services.training_eligibility_service import TrainingEligibilityService
from db.repositories.types import AuthIdentity
from db.repositories import SQLAlchemyAdminRepository, SQLAlchemyWhitelistRepository
from db.session import get_db

router = APIRouter()
settings = get_settings()
LOGIN_SUCCESS_REDIRECT = "/announcements"


def _path(request: Request, suffix: str = "") -> str:
    return f"{get_settings().path_base}{suffix}"


def _clear_login_session(request: Request) -> None:
    request.session.pop("auth_context", None)
    request.session.pop("csrf_token", None)
    request.session.pop("oauth_request_id", None)
    request.session.pop("oauth_state", None)


def _build_login_error_redirect(*, route: str, reason: str, request_id: str) -> RedirectResponse:
    query = urlencode({"route": route, "reason": reason, "request_id": request_id})
    return RedirectResponse(f"{get_settings().path_base}/login-error?{query}", status_code=302)


def _log_auth_audit_or_redirect(
    *,
    request: Request,
    audit: AuthAuditService,
    route: str,
    reason: str,
    request_id: str,
    payload: dict,
) -> RedirectResponse | None:
    try:
        audit.log(**payload)
    except Exception:
        _clear_login_session(request)
        return _build_login_error_redirect(route=route, reason=reason, request_id=request_id)
    return None


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
    request_id = getattr(request.state, "request_id", str(uuid4()))
    current_settings = get_settings()
    env = current_settings.app_env.lower()
    if env == "dev":
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
        return RedirectResponse(_path(request, LOGIN_SUCCESS_REDIRECT), status_code=302)

    _clear_login_session(request)
    try:
        service = OAuthService()
        return RedirectResponse(service.build_login_url(request), status_code=302)
    except ApiError:
        raise
    except Exception:
        _clear_login_session(request)
        return _build_login_error_redirect(route="login", reason="login_redirect_failed", request_id=request_id)


@router.get(
    "/auth/callback",
    status_code=302,
    response_class=RedirectResponse,
    dependencies=[enforce_rate_limit("oauth_callback", settings.login_rate_limit)],
    responses={
        302: {"description": "FISA callback success and redirect to frontend"},
        401: {"model": ErrorResponse, "description": "FISA authentication failed"},
        422: {"model": ErrorResponse, "description": "OAuth callback payload is invalid"},
    },
)
def oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    current_settings = get_settings()
    provider = "fisa"
    request_id = getattr(request.state, "request_id", str(uuid4()))
    audit = AuthAuditService(db)
    expected_state = request.session.pop("oauth_state", None)
    request.session.pop("oauth_request_id", None)
    # State is single-use. Every invalid callback clears any previous login.
    if not state or not expected_state or not secrets.compare_digest(state, expected_state):
        _clear_login_session(request)
        redirect = _log_auth_audit_or_redirect(
            request=request, audit=audit, route="auth_callback", reason="audit_log_failed",
            request_id=request_id,
            payload={"provider": provider, "request_id": request_id, "result": "failure", "error_code": "OAUTH_STATE_INVALID"},
        )
        if redirect is not None:
            return redirect
        raise ApiError("OAUTH_STATE_INVALID", "oauth state invalid", 422)
    if not code:
        _clear_login_session(request)
        redirect = _log_auth_audit_or_redirect(
            request=request, audit=audit, route="auth_callback", reason="audit_log_failed",
            request_id=request_id,
            payload={"provider": provider, "request_id": request_id, "result": "failure", "error_code": "OAUTH_CODE_MISSING"},
        )
        if redirect is not None:
            return redirect
        raise ApiError("OAUTH_CODE_MISSING", "oauth code missing", 422)

    try:
        oauth = OAuthService()
        token = oauth.exchange_code_for_token(code)
        identity = oauth.fetch_identity(token)
    except ApiError as exc:
        _clear_login_session(request)
        redirect = _log_auth_audit_or_redirect(
            request=request, audit=audit, route="auth_callback", reason="audit_log_failed",
            request_id=request_id,
            payload={"provider": provider, "request_id": request_id, "result": "failure", "error_code": exc.code},
        )
        if redirect is not None:
            return redirect
        raise ApiError(exc.code, f"{exc.message}; request_id={request_id}", exc.status_code) from exc
    except Exception:
        _clear_login_session(request)
        return _build_login_error_redirect(route="auth_callback", reason="oauth_exchange_failed", request_id=request_id)

    if not current_settings.fisa_sysid_is_datahub_sso_confirmed:
        _clear_login_session(request)
        redirect = _log_auth_audit_or_redirect(
            request=request, audit=audit, route="auth_callback", reason="audit_log_failed",
            request_id=request_id,
            payload={"provider": provider, "request_id": request_id, "result": "failure", "error_code": "TRAINING_IDENTITY_UNAVAILABLE"},
        )
        if redirect is not None:
            return redirect
        return RedirectResponse(_path(request, "/login-denied") + "?error=TRAINING_SERVICE_UNAVAILABLE", status_code=302)

    eligibility = LoginEligibilityService(
        whitelist_repo=SQLAlchemyWhitelistRepository(db),
        admin_repo=SQLAlchemyAdminRepository(db),
    )
    gate = LoginQualificationGate(
        training=TrainingEligibilityService(),
        existing=eligibility,
        audit=audit,
    )
    result = gate.evaluate(
        trusted_sso=identity.raw_sysid,
        sysid=identity.sysid,
        tcode=identity.tcode,
        session=request.session,
        provider=provider,
        request_id=request_id,
    )
    if result.status != GateStatus.ALLOWED:
        error = {
            GateStatus.TRAINING_INCOMPLETE: "TRAINING_INCOMPLETE",
            GateStatus.LOGIN_NOT_ELIGIBLE: "LOGIN_NOT_ELIGIBLE",
            GateStatus.SERVICE_UNAVAILABLE: "TRAINING_SERVICE_UNAVAILABLE",
        }[result.status]
        return RedirectResponse(_path(request, "/login-denied") + f"?error={error}", status_code=302)

    try:
        request.session["auth_context"] = {
            "account": identity.account,
            "name": identity.name,
            "email": identity.email,
            "department": identity.department,
            "sysid": identity.sysid,
            "raw_sysid": identity.raw_sysid,
            "role": "user",
        }
        ensure_csrf_token(request)
    except Exception:
        _clear_login_session(request)
        return _build_login_error_redirect(route="auth_callback", reason="session_init_failed", request_id=request_id)
    redirect = _log_auth_audit_or_redirect(
        request=request, audit=audit, route="auth_callback", reason="audit_log_failed",
        request_id=request_id,
        payload={
            "provider": provider, "request_id": request_id, "result": "success",
        },
    )
    if redirect is not None:
        return redirect
    return RedirectResponse(_path(request, LOGIN_SUCCESS_REDIRECT), status_code=302)


@router.post("/logout", dependencies=[Depends(csrf_protected), enforce_rate_limit("logout", settings.login_rate_limit)])
def logout(request: Request) -> dict[str, str]:
    request.session.pop("auth_context", None)
    request.session.pop("csrf_token", None)
    return {"status": "ok"}

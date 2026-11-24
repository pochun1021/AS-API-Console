from uuid import uuid4
import secrets
from typing import Literal
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.security import csrf_protected, enforce_rate_limit, ensure_csrf_token
from app.schemas.common import ErrorResponse
from app.services.auth_audit_service import AuthAuditService
from app.services.datahub_client import DataHubError, DataHubErrorKind
from app.services.login_eligibility_service import LoginEligibilityService
from app.services.oauth_service import OAuthService
from app.services.login_qualification_gate import (
    GateStatus,
    LoginQualificationGate,
    TRAINING_INCOMPLETE_MESSAGE,
    TRAINING_UNAVAILABLE_MESSAGE,
)
from app.services.training_eligibility_service import TrainingEligibilityService
from db.repositories.types import AuthIdentity
from db.repositories import SQLAlchemyAdminRepository, SQLAlchemyWhitelistRepository
from db.session import get_db

router = APIRouter()
settings = get_settings()
LOGIN_SUCCESS_REDIRECT = "/announcements"


class LocalLoginPayload(BaseModel):
    account: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr = Field(max_length=255)
    department: str = Field(min_length=1, max_length=100)
    sysid: int = Field(gt=0, le=9223372036854775807)
    role: Literal["user", "admin"] = "user"


def _require_local_login() -> None:
    if get_settings().app_env.lower() not in {"dev", "test"}:
        raise HTTPException(status_code=404)


@router.get("/auth/local-login", include_in_schema=False)
def local_login_defaults() -> dict[str, str | int | None]:
    _require_local_login()
    current_settings = get_settings()
    role = current_settings.dev_login_role.strip().lower()
    if role not in {"user", "admin"}:
        raise ApiError("INTERNAL_ERROR", "invalid DEV_LOGIN_ROLE: must be user or admin", 500)
    return {
        "account": current_settings.dev_login_account or "",
        "name": current_settings.dev_login_name or "",
        "email": current_settings.dev_login_email or "",
        "department": current_settings.dev_login_department or "",
        "sysid": current_settings.dev_login_sysid,
        "role": role,
    }


@router.post(
    "/auth/local-login",
    include_in_schema=False,
    dependencies=[Depends(_require_local_login), enforce_rate_limit("local_login", settings.login_rate_limit)],
)
def create_local_login_session(
    payload: LocalLoginPayload,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    _require_local_login()
    identity = payload.model_dump()
    for field in ("account", "name", "department"):
        identity[field] = identity[field].strip()
        if not identity[field]:
            raise ApiError("VALIDATION_ERROR", f"{field} is required", 422)
    identity["email"] = str(payload.email).lower()
    _clear_login_session(request)
    warning = None
    try:
        incomplete = TrainingEligibilityService().is_incomplete(trusted_sso=str(payload.sysid))
    except DataHubError as exc:
        if exc.kind not in {DataHubErrorKind.NETWORK, DataHubErrorKind.TIMEOUT}:
            raise ApiError("TRAINING_SERVICE_UNAVAILABLE", TRAINING_UNAVAILABLE_MESSAGE, 503) from None
        warning = "DATAHUB_CONNECTION_FAILED"
        incomplete = False
    except Exception:
        raise ApiError("TRAINING_SERVICE_UNAVAILABLE", TRAINING_UNAVAILABLE_MESSAGE, 503) from None
    if incomplete:
        raise ApiError("TRAINING_INCOMPLETE", TRAINING_INCOMPLETE_MESSAGE, 403)
    if payload.role == "admin":
        SQLAlchemyAdminRepository(db).upsert_from_auth(
            AuthIdentity(
                account=identity["account"],
                name=identity["name"],
                email=identity["email"],
                department=identity["department"],
                sysid=payload.sysid,
            ),
            created_by=identity["account"],
        )
        db.commit()
    identity["auth_source"] = "local_login"
    request.session["auth_context"] = identity
    ensure_csrf_token(request)
    response = {"redirect": _path(request, LOGIN_SUCCESS_REDIRECT)}
    if warning:
        response["warning"] = warning
    return response


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
        302: {"description": "Redirect to local sign-in page or OAuth provider"},
        500: {"model": ErrorResponse, "description": "OAuth configuration is invalid or incomplete"},
    },
)
def login(
    request: Request,
) -> RedirectResponse:
    request_id = getattr(request.state, "request_id", str(uuid4()))
    current_settings = get_settings()
    env = current_settings.app_env.lower()
    if env in {"dev", "test"}:
        _clear_login_session(request)
        return RedirectResponse(_path(request, "/local-login"), status_code=302)
    if env != "prod":
        raise ApiError("INTERNAL_ERROR", "unsupported APP_ENV", 500)

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
    if current_settings.app_env.lower() != "prod":
        raise HTTPException(status_code=404)
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

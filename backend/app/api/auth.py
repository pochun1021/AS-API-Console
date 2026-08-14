from uuid import uuid4
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
from app.services.persnl_soap_service import PersnlSoapUnavailableError
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
    request.session.pop("oauth_nonce", None)
    request.session.pop("oauth_code_verifier", None)


def _build_login_error_redirect(*, route: str, reason: str, request_id: str) -> RedirectResponse:
    query = urlencode({"route": route, "reason": reason, "request_id": request_id})
    return RedirectResponse(f"{get_settings().path_base}/login-error?{query}", status_code=302)


def _test_oauth_fallback_identity(settings, google_identity):
    if settings.app_env.lower() != "test":
        return None
    required = {
        "TEST_OAUTH_ACCOUNT": settings.test_oauth_account,
        "TEST_OAUTH_NAME": settings.test_oauth_name,
        "TEST_OAUTH_EMAIL": settings.test_oauth_email,
        "TEST_OAUTH_DEPARTMENT": settings.test_oauth_department,
        "TEST_OAUTH_SYSID": settings.test_oauth_sysid,
        "TEST_OAUTH_TCODE": settings.test_oauth_tcode,
    }
    if any(value is None or (isinstance(value, str) and not value.strip()) for value in required.values()):
        raise ApiError("SOAP_SERVICE_UNAVAILABLE", "personnel directory unavailable", 503)
    if settings.test_oauth_sysid <= 0:
        raise ApiError("SOAP_SERVICE_UNAVAILABLE", "personnel directory unavailable", 503)
    if settings.test_oauth_email.strip().lower() != google_identity.email.lower():
        raise ApiError("OAUTH_IDENTITY_INVALID", "test oauth identity email does not match Google email", 422)
    return type(google_identity)(
        account=settings.test_oauth_account.strip(),
        name=settings.test_oauth_name.strip(),
        email=settings.test_oauth_email.strip().lower(),
        department=settings.test_oauth_department.strip(),
        sysid=settings.test_oauth_sysid,
        tcode=settings.test_oauth_tcode.strip(),
        role="user",
    )


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

    try:
        ensure_csrf_token(request)
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
        302: {"description": "OAuth callback success and redirect to frontend"},
        401: {"model": ErrorResponse, "description": "OAuth provider authentication failed"},
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
    provider = current_settings.oauth_provider
    request_id = state or str(uuid4())
    audit = AuthAuditService(db)

    expected_state = request.session.pop("oauth_state", None)
    expected_nonce = request.session.pop("oauth_nonce", None)
    code_verifier = request.session.pop("oauth_code_verifier", None)
    if not state or not expected_state or state != expected_state or not expected_nonce:
        redirect = _log_auth_audit_or_redirect(
            request=request,
            audit=audit,
            route="auth_callback",
            reason="audit_log_failed",
            request_id=request_id,
            payload={
                "provider": provider,
                "request_id": request_id,
                "result": "failure",
                "error_code": "OAUTH_STATE_INVALID",
            },
        )
        if redirect is not None:
            return redirect
        raise ApiError("OAUTH_STATE_INVALID", "oauth state invalid", 422)

    if not code:
        redirect = _log_auth_audit_or_redirect(
            request=request,
            audit=audit,
            route="auth_callback",
            reason="audit_log_failed",
            request_id=request_id,
            payload={
                "provider": provider,
                "request_id": request_id,
                "result": "failure",
                "error_code": "OAUTH_CODE_MISSING",
            },
        )
        if redirect is not None:
            return redirect
        raise ApiError("OAUTH_CODE_MISSING", "oauth callback code missing", 422)

    oauth = OAuthService()
    try:
        token = oauth.exchange_code_for_token(code, code_verifier=code_verifier)
        identity = oauth.fetch_identity(token, expected_nonce=expected_nonce)
        if identity.sysid == 0:
            fallback_used = False
            try:
                person = request.app.state.persnl_soap_service.find_unique_person_by_account(identity.account)
            except PersnlSoapUnavailableError as exc:
                fallback = _test_oauth_fallback_identity(current_settings, identity)
                if fallback is None:
                    raise ApiError("SOAP_SERVICE_UNAVAILABLE", "personnel directory unavailable", 503) from exc
                identity = fallback
                fallback_used = True
                person = None
            if person is None and not fallback_used:
                raise ApiError("OAUTH_IDENTITY_INVALID", "google account not found in personnel directory", 422)
            if person is not None and person.get("email", "").lower() != identity.email.lower():
                raise ApiError("OAUTH_IDENTITY_INVALID", "google account not found in personnel directory", 422)
            if person is not None:
                identity = type(identity)(
                    account=person["cn"],
                    name=person["chName"],
                    email=person["email"].lower(),
                    department=person["instCode"],
                    sysid=int(person["sysId"]),
                    tcode=person["tCode"],
                    role="user",
                )
    except ApiError as exc:
        redirect = _log_auth_audit_or_redirect(
            request=request,
            audit=audit,
            route="auth_callback",
            reason="audit_log_failed",
            request_id=request_id,
            payload={
                "provider": provider,
                "request_id": request_id,
                "result": "failure",
                "error_code": exc.code,
            },
        )
        if redirect is not None:
            return redirect
        raise ApiError(exc.code, f"{exc.message}; request_id={request_id}", exc.status_code) from exc
    except Exception:
        _clear_login_session(request)
        return _build_login_error_redirect(route="auth_callback", reason="oauth_exchange_failed", request_id=request_id)

    eligibility = LoginEligibilityService(
        whitelist_repo=SQLAlchemyWhitelistRepository(db),
        admin_repo=SQLAlchemyAdminRepository(db),
    )
    try:
        is_eligible = eligibility.is_eligible(sysid=identity.sysid, tcode=identity.tcode)
    except Exception:
        _clear_login_session(request)
        return _build_login_error_redirect(route="auth_callback", reason="eligibility_check_failed", request_id=request_id)

    if not is_eligible:
        redirect = _log_auth_audit_or_redirect(
            request=request,
            audit=audit,
            route="auth_callback",
            reason="audit_log_failed",
            request_id=request_id,
            payload={
                "provider": provider,
                "request_id": request_id,
                "result": "failure",
                "account": identity.account,
                "name": identity.name,
                "email": identity.email,
                "department": identity.department,
                "sysid": identity.sysid,
                "role": "user",
                "error_code": "LOGIN_NOT_ELIGIBLE",
            },
        )
        if redirect is not None:
            return redirect
        return RedirectResponse(_path(request, "/login-denied") + "?error=LOGIN_NOT_ELIGIBLE", status_code=302)

    try:
        request.session["auth_context"] = {
            "account": identity.account,
            "name": identity.name,
            "email": identity.email.lower(),
            "department": identity.department,
            "sysid": identity.sysid,
            "role": "user",
        }
        ensure_csrf_token(request)
    except Exception:
        _clear_login_session(request)
        return _build_login_error_redirect(route="auth_callback", reason="session_init_failed", request_id=request_id)

    redirect = _log_auth_audit_or_redirect(
        request=request,
        audit=audit,
        route="auth_callback",
        reason="audit_log_failed",
        request_id=request_id,
        payload={
            "provider": provider,
            "request_id": request_id,
            "result": "success",
            "account": identity.account,
            "name": identity.name,
            "email": identity.email,
            "department": identity.department,
            "sysid": identity.sysid,
            "role": "user",
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

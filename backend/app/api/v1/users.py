from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.security import csrf_protected, enforce_rate_limit, ensure_csrf_token, validate_search_keyword
from app.schemas.common import ErrorResponse
from app.services.operation_audit_service import OperationAuditService, extract_request_audit_context
from app.schemas.users import (
    AdminCreateRequest,
    CurrentUserResponse,
    UserListResponse,
    UserLocalePreferenceResponse,
    UserLocalePreferenceUpdateRequest,
    UserRoleMutationResponse,
)
from app.services.users_service import UsersService
from db.session import get_db

router = APIRouter()
settings = get_settings()


def _require_admin(current_user: CurrentUser) -> None:
    if current_user.role != "admin":
        raise ApiError("VALIDATION_ERROR", "admin role required", 403)


def _parse_admin_id(user_id: str) -> int:
    if not user_id.isdigit():
        raise ApiError("VALIDATION_ERROR", "admin id must be numeric", 422)
    parsed = int(user_id)
    if parsed <= 0:
        raise ApiError("VALIDATION_ERROR", "admin id must be positive integer", 422)
    return parsed


@router.get("/users/me", response_model=CurrentUserResponse)
def get_current_user_profile(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    if "auth_context" not in request.session:
        request.session["auth_context"] = {
            "account": current_user.account,
            "name": current_user.name,
            "email": current_user.email,
            "department": current_user.department,
            "sysid": current_user.sysid,
            "role": current_user.role,
        }
    return {
        "account": current_user.account,
        "name": current_user.name,
        "email": current_user.email,
        "department": current_user.department,
        "sysid": current_user.sysid,
        "role": current_user.role,
        "csrf_token": ensure_csrf_token(request),
    }


@router.get(
    "/admins",
    response_model=UserListResponse,
    responses={
        403: {"model": ErrorResponse, "description": "Admin role is required"},
    },
)
def list_admins(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_admin(current_user)
    service = UsersService(db)
    return service.list_admins()


@router.get(
    "/users",
    response_model=UserListResponse,
    responses={
        403: {"model": ErrorResponse, "description": "Admin role is required"},
        422: {"model": ErrorResponse, "description": "Query parameters are invalid"},
        503: {"model": ErrorResponse, "description": "Directory service is unavailable"},
    },
)
def list_users(
    request: Request,
    q: str = Query(...),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_admin(current_user)
    validate_search_keyword(q)
    service = UsersService(db, persnl_service=request.app.state.persnl_soap_service)
    return service.search(q=q)


@router.post(
    "/admins/{user_id}/enable",
    response_model=UserRoleMutationResponse,
    dependencies=[Depends(csrf_protected), enforce_rate_limit("admin-enable", settings.admin_mutation_rate_limit)],
)
def enable_admin(
    user_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    audit = OperationAuditService(db)
    context = extract_request_audit_context(request)
    event_type = "admin_management"
    action = "enable"
    target_type = "admin"
    target_id = user_id
    parsed_admin_id = _parse_admin_id(user_id)
    try:
        _require_admin(current_user)
    except ApiError as exc:
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code=exc.code,
            actor=current_user,
            target_type=target_type,
            target_id=target_id,
            context=context,
            metadata={"target_admin_id": user_id},
        )
        raise

    service = UsersService(db)
    try:
        result = service.enable_admin(current_user=current_user, user_id=parsed_admin_id)
    except ApiError as exc:
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code=exc.code,
            actor=current_user,
            target_type=target_type,
            target_id=target_id,
            context=context,
            metadata={"target_admin_id": user_id},
        )
        raise
    except Exception:
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code="INTERNAL_ERROR",
            actor=current_user,
            target_type=target_type,
            target_id=target_id,
            context=context,
            metadata={"target_admin_id": user_id},
        )
        raise

    audit.log(
        event_type=event_type,
        action=action,
        result="success",
        actor=current_user,
        target_type=target_type,
        target_id=result["id"],
        context=context,
        metadata={"target_admin_id": result["id"], "status": result["status"]},
    )
    return result


@router.put(
    "/admins/{user_id}",
    response_model=UserRoleMutationResponse,
    dependencies=[Depends(csrf_protected), enforce_rate_limit("admin-create", settings.admin_mutation_rate_limit)],
    responses={
        403: {"model": ErrorResponse, "description": "Admin role is required"},
        404: {"model": ErrorResponse, "description": "Admin user was not found"},
        409: {"model": ErrorResponse, "description": "Admin already exists"},
        422: {"model": ErrorResponse, "description": "Request body or path parameter is invalid"},
    },
)
def create_admin(
    user_id: str,
    payload: AdminCreateRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    audit = OperationAuditService(db)
    context = extract_request_audit_context(request)
    event_type = "admin_management"
    action = "create"
    target_type = "admin"
    target_id = user_id
    parsed_admin_id = _parse_admin_id(user_id)
    try:
        _require_admin(current_user)
    except ApiError as exc:
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code=exc.code,
            actor=current_user,
            target_type=target_type,
            target_id=target_id,
            context=context,
            metadata={"target_admin_id": user_id},
        )
        raise

    service = UsersService(db)
    try:
        result = service.create_admin(
            current_user=current_user,
            user_id=parsed_admin_id,
            account=payload.account,
            name=payload.name,
            email=payload.email,
            department=payload.department,
        )
    except ApiError as exc:
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code=exc.code,
            actor=current_user,
            target_type=target_type,
            target_id=target_id,
            context=context,
            metadata={"target_admin_id": user_id},
        )
        raise
    except Exception:
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code="INTERNAL_ERROR",
            actor=current_user,
            target_type=target_type,
            target_id=target_id,
            context=context,
            metadata={"target_admin_id": user_id},
        )
        raise

    audit.log(
        event_type=event_type,
        action=action,
        result="success",
        actor=current_user,
        target_type=target_type,
        target_id=result["id"],
        context=context,
        metadata={"target_admin_id": result["id"], "status": result["status"]},
    )
    return result


@router.post(
    "/admins/{user_id}/disable",
    response_model=UserRoleMutationResponse,
    dependencies=[Depends(csrf_protected), enforce_rate_limit("admin-disable", settings.admin_mutation_rate_limit)],
)
def disable_admin(
    user_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    audit = OperationAuditService(db)
    context = extract_request_audit_context(request)
    event_type = "admin_management"
    action = "disable"
    target_type = "admin"
    target_id = user_id
    parsed_admin_id = _parse_admin_id(user_id)
    try:
        _require_admin(current_user)
    except ApiError as exc:
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code=exc.code,
            actor=current_user,
            target_type=target_type,
            target_id=target_id,
            context=context,
            metadata={"target_admin_id": user_id},
        )
        raise

    service = UsersService(db)
    try:
        result = service.disable_admin(current_user=current_user, user_id=parsed_admin_id)
    except ApiError as exc:
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code=exc.code,
            actor=current_user,
            target_type=target_type,
            target_id=target_id,
            context=context,
            metadata={"target_admin_id": user_id},
        )
        raise
    except Exception:
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code="INTERNAL_ERROR",
            actor=current_user,
            target_type=target_type,
            target_id=target_id,
            context=context,
            metadata={"target_admin_id": user_id},
        )
        raise

    audit.log(
        event_type=event_type,
        action=action,
        result="success",
        actor=current_user,
        target_type=target_type,
        target_id=result["id"],
        context=context,
        metadata={"target_admin_id": result["id"], "status": result["status"]},
    )
    return result


@router.delete(
    "/admins/{user_id}",
    status_code=204,
    dependencies=[Depends(csrf_protected), enforce_rate_limit("admin-delete", settings.admin_mutation_rate_limit)],
    responses={
        403: {"model": ErrorResponse, "description": "Admin role is required"},
        404: {"model": ErrorResponse, "description": "Admin user was not found"},
        422: {"model": ErrorResponse, "description": "Active admin cannot be deleted"},
    },
)
def delete_admin(
    user_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    audit = OperationAuditService(db)
    context = extract_request_audit_context(request)
    event_type = "admin_management"
    action = "delete"
    target_type = "admin"
    target_id = user_id
    parsed_admin_id = _parse_admin_id(user_id)
    try:
        _require_admin(current_user)
    except ApiError as exc:
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code=exc.code,
            actor=current_user,
            target_type=target_type,
            target_id=target_id,
            context=context,
            metadata={"target_admin_id": user_id},
        )
        raise

    service = UsersService(db)
    try:
        service.delete_inactive_admin(current_user=current_user, user_id=parsed_admin_id)
    except ApiError as exc:
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code=exc.code,
            actor=current_user,
            target_type=target_type,
            target_id=target_id,
            context=context,
            metadata={"target_admin_id": user_id},
        )
        raise
    except Exception:
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code="INTERNAL_ERROR",
            actor=current_user,
            target_type=target_type,
            target_id=target_id,
            context=context,
            metadata={"target_admin_id": user_id},
        )
        raise

    audit.log(
        event_type=event_type,
        action=action,
        result="success",
        actor=current_user,
        target_type=target_type,
        target_id=user_id,
        context=context,
        metadata={"target_admin_id": user_id},
    )


@router.get("/users/preferences/locale", response_model=UserLocalePreferenceResponse)
def get_locale_preference(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    service = UsersService(db)
    return service.get_locale_preference(current_user)


@router.patch("/users/preferences/locale", response_model=UserLocalePreferenceResponse, dependencies=[Depends(csrf_protected)])
def update_locale_preference(
    payload: UserLocalePreferenceUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    service = UsersService(db)
    return service.update_locale_preference(current_user=current_user, preferred_locale=payload.preferred_locale)

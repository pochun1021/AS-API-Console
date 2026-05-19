from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.errors import ApiError
from app.services.operation_audit_service import OperationAuditService, extract_request_audit_context
from app.schemas.users import (
    UserListResponse,
    UserLocalePreferenceResponse,
    UserLocalePreferenceUpdateRequest,
    UserRoleMutationResponse,
)
from app.services.users_service import UsersService
from db.session import get_db

router = APIRouter()


def _require_admin(current_user: CurrentUser) -> None:
    if current_user.role != "admin":
        raise ApiError("VALIDATION_ERROR", "admin role required", 403)


@router.get("/users", response_model=UserListResponse)
def list_users(
    q: str = Query(default=""),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_admin(current_user)
    service = UsersService(db)
    return service.search(q=q)


@router.post("/admins/{user_id}/enable", response_model=UserRoleMutationResponse)
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
        result = service.enable_admin(current_user=current_user, user_id=user_id)
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


@router.post("/admins/{user_id}/disable", response_model=UserRoleMutationResponse)
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
        result = service.disable_admin(current_user=current_user, user_id=user_id)
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


@router.get("/users/preferences/locale", response_model=UserLocalePreferenceResponse)
def get_locale_preference(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    service = UsersService(db)
    return service.get_locale_preference(current_user)


@router.patch("/users/preferences/locale", response_model=UserLocalePreferenceResponse)
def update_locale_preference(
    payload: UserLocalePreferenceUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    service = UsersService(db)
    return service.update_locale_preference(current_user=current_user, preferred_locale=payload.preferred_locale)

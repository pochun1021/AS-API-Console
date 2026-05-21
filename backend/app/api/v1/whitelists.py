from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.security import csrf_protected, enforce_rate_limit
from app.services.operation_audit_service import OperationAuditService, extract_request_audit_context
from app.schemas.whitelists import (
    WhitelistCreateRequest,
    WhitelistItemResponse,
    WhitelistListResponse,
    WhitelistUpdateRequest,
)
from app.services.whitelists_service import WhitelistsService
from db.session import get_db

router = APIRouter()
settings = get_settings()


def _require_admin(current_user: CurrentUser) -> None:
    if current_user.role != "admin":
        raise ApiError("VALIDATION_ERROR", "admin role required", 403)


@router.post(
    "/whitelists",
    response_model=WhitelistItemResponse,
    status_code=201,
    dependencies=[Depends(csrf_protected), enforce_rate_limit("whitelist-create", settings.admin_mutation_rate_limit)],
)
def create_whitelist(
    payload: WhitelistCreateRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    audit = OperationAuditService(db)
    context = extract_request_audit_context(request)
    event_type = "whitelist"
    action = "create"
    target_type = "whitelist"
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
            context=context,
            metadata={"sysid": payload.sysid},
        )
        raise

    service = WhitelistsService(db)
    try:
        result = service.create(current_user, payload.sysid, payload.note)
    except ApiError as exc:
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code=exc.code,
            actor=current_user,
            target_type=target_type,
            context=context,
            metadata={"sysid": payload.sysid},
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
            context=context,
            metadata={"sysid": payload.sysid},
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
        metadata={"whitelist_id": result["id"], "sysid": result["sysid"], "status": result["status"]},
    )
    return result


@router.get("/whitelists", response_model=WhitelistListResponse)
def list_whitelists(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_admin(current_user)
    service = WhitelistsService(db)
    return service.list(status=status, page=page, page_size=page_size)


@router.patch(
    "/whitelists/{whitelist_id}",
    response_model=WhitelistItemResponse,
    dependencies=[Depends(csrf_protected), enforce_rate_limit("whitelist-update", settings.admin_mutation_rate_limit)],
)
def update_whitelist(
    whitelist_id: str,
    payload: WhitelistUpdateRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    audit = OperationAuditService(db)
    context = extract_request_audit_context(request)
    event_type = "whitelist"
    action = "update"
    target_type = "whitelist"
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
            target_id=whitelist_id,
            context=context,
            metadata={"whitelist_id": whitelist_id, "status": payload.status},
        )
        raise

    service = WhitelistsService(db)
    try:
        result = service.update(current_user, whitelist_id, payload.status, payload.note)
    except ApiError as exc:
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code=exc.code,
            actor=current_user,
            target_type=target_type,
            target_id=whitelist_id,
            context=context,
            metadata={"whitelist_id": whitelist_id, "status": payload.status},
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
            target_id=whitelist_id,
            context=context,
            metadata={"whitelist_id": whitelist_id, "status": payload.status},
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
        metadata={"whitelist_id": result["id"], "status": result["status"]},
    )
    return result

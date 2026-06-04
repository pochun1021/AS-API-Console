from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.security import csrf_protected, enforce_rate_limit
from app.schemas.common import ErrorResponse
from app.schemas.institutes import InstituteListResponse, InstituteSyncResponse
from app.services.institute_sync_service import InstituteSyncService
from app.services.institutes_service import InstitutesService
from app.services.operation_audit_service import (
    OperationAuditService,
    extract_request_audit_context,
    summarize_operation_audit_error,
)
from app.services.persnl_soap_service import PersnlSoapUnavailableError
from db.session import get_db

router = APIRouter()
settings = get_settings()


def _require_admin(current_user: CurrentUser) -> None:
    if current_user.role != "admin":
        raise ApiError("VALIDATION_ERROR", "admin role required", 403)


@router.get("/institutes", response_model=InstituteListResponse)
def list_institutes(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _ = current_user
    service = InstitutesService(db)
    return service.list_active()


@router.post(
    "/institutes/sync",
    response_model=InstituteSyncResponse,
    dependencies=[Depends(csrf_protected), enforce_rate_limit("institutes-sync", settings.admin_mutation_rate_limit)],
    responses={
        403: {"model": ErrorResponse, "description": "CSRF token is invalid or admin role is required"},
        503: {"model": ErrorResponse, "description": "SOAP service is unavailable"},
    },
)
def sync_institutes(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    audit = OperationAuditService(db)
    context = extract_request_audit_context(request)
    event_type = "institute_sync"
    action = "sync"
    target_type = "institute"
    try:
        _require_admin(current_user)
        remote_institutes = request.app.state.persnl_soap_service.get_institutes()
        result = InstituteSyncService(db).sync(remote_institutes, dry_run=False)
    except ApiError as exc:
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code=exc.code,
            error_detail=summarize_operation_audit_error(exc),
            actor=current_user,
            target_type=target_type,
            context=context,
        )
        raise
    except PersnlSoapUnavailableError as exc:
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code="SOAP_SERVICE_UNAVAILABLE",
            error_detail=summarize_operation_audit_error(exc),
            actor=current_user,
            target_type=target_type,
            context=context,
        )
        raise ApiError("SOAP_SERVICE_UNAVAILABLE", "soap service unavailable", 503) from exc
    except Exception as exc:
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code="INTERNAL_ERROR",
            error_detail=summarize_operation_audit_error(exc),
            actor=current_user,
            target_type=target_type,
            context=context,
        )
        raise

    payload = {
        "fetched_count": result.fetched_count,
        "inserted_count": result.inserted_count,
        "updated_count": result.updated_count,
        "unchanged_count": result.unchanged_count,
        "deactivated_count": result.deactivated_count,
    }
    audit.log(
        event_type=event_type,
        action=action,
        result="success",
        actor=current_user,
        target_type=target_type,
        context=context,
        metadata=payload,
    )
    return payload

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.security import csrf_protected, enforce_rate_limit
from app.schemas.announcements import (
    AnnouncementCreateRequest,
    AnnouncementItemResponse,
    AnnouncementListResponse,
    AnnouncementUpdateRequest,
)
from app.schemas.common import ErrorResponse
from app.services.announcements_service import AnnouncementsService
from app.services.operation_audit_service import (
    OperationAuditService,
    extract_request_audit_context,
    summarize_operation_audit_error,
)
from db.session import get_db

router = APIRouter()
settings = get_settings()


def _require_admin(current_user: CurrentUser) -> None:
    if current_user.role != "admin":
        raise ApiError("FORBIDDEN", "admin role required", 403)


@router.get(
    "/announcements",
    response_model=AnnouncementListResponse,
    responses={
        403: {"model": ErrorResponse, "description": "Admin role is required for scope=all"},
        422: {"model": ErrorResponse, "description": "Request query is invalid"},
    },
)
def list_announcements(
    request: Request,
    scope: str | None = Query(default=None),
    status: str | None = Query(default=None),
    title: str | None = Query(default=None),
    publish_from_from: datetime | None = Query(default=None),
    publish_from_to: datetime | None = Query(default=None),
    publish_to_from: datetime | None = Query(default=None),
    publish_to_to: datetime | None = Query(default=None),
    updated_from: datetime | None = Query(default=None),
    updated_to: datetime | None = Query(default=None),
    sort_by: str = Query(default="updated_at"),
    sort_dir: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    audit = OperationAuditService(db)
    context = extract_request_audit_context(request)
    service = AnnouncementsService(db)
    try:
        result = service.list(
            current_user=current_user,
            scope=scope,
            status=status,
            title=title,
            publish_from_from=publish_from_from,
            publish_from_to=publish_from_to,
            publish_to_from=publish_to_from,
            publish_to_to=publish_to_to,
            updated_from=updated_from,
            updated_to=updated_to,
            sort_by=sort_by,
            sort_dir=sort_dir,
            page=page,
            page_size=page_size,
        )
    except ApiError as exc:
        audit.log(
            event_type="announcement_management",
            action="list",
            result="failure",
            error_code=exc.code,
            error_detail=summarize_operation_audit_error(exc),
            actor=current_user,
            target_type="announcement",
            context=context,
            metadata={"matched_count": 0},
        )
        raise
    except Exception as exc:
        audit.log(
            event_type="announcement_management",
            action="list",
            result="failure",
            error_code="INTERNAL_ERROR",
            error_detail=summarize_operation_audit_error(exc),
            actor=current_user,
            target_type="announcement",
            context=context,
            metadata={"matched_count": 0},
        )
        raise

    audit.log(
        event_type="announcement_management",
        action="list",
        result="success",
        actor=current_user,
        target_type="announcement",
        context=context,
        metadata={"matched_count": result["total"]},
    )
    return result


@router.post(
    "/announcements",
    response_model=AnnouncementItemResponse,
    status_code=201,
    dependencies=[Depends(csrf_protected), enforce_rate_limit("announcement-create", settings.admin_mutation_rate_limit)],
    responses={
        403: {"model": ErrorResponse, "description": "CSRF token is invalid or admin role is required"},
        422: {"model": ErrorResponse, "description": "Request payload is invalid"},
    },
)
def create_announcement(
    payload: AnnouncementCreateRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    audit = OperationAuditService(db)
    context = extract_request_audit_context(request)
    try:
        _require_admin(current_user)
        result = AnnouncementsService(db).create(
            current_user,
            title=payload.title,
            body=payload.body,
            status=payload.status,
            publish_from=payload.publish_from,
            publish_to=payload.publish_to,
        )
    except ApiError as exc:
        audit.log(
            event_type="announcement_management",
            action="create",
            result="failure",
            error_code=exc.code,
            error_detail=summarize_operation_audit_error(exc),
            actor=current_user,
            target_type="announcement",
            context=context,
            metadata={"status": payload.status, "title": payload.title},
        )
        raise
    except Exception as exc:
        audit.log(
            event_type="announcement_management",
            action="create",
            result="failure",
            error_code="INTERNAL_ERROR",
            error_detail=summarize_operation_audit_error(exc),
            actor=current_user,
            target_type="announcement",
            context=context,
            metadata={"status": payload.status, "title": payload.title},
        )
        raise

    audit.log(
        event_type="announcement_management",
        action="create",
        result="success",
        actor=current_user,
        target_type="announcement",
        target_id=result["id"],
        context=context,
        metadata={"announcement_id": result["id"], "status": result["status"], "title": result["title"]},
    )
    return result


@router.patch(
    "/announcements/{announcement_id}",
    response_model=AnnouncementItemResponse,
    dependencies=[Depends(csrf_protected), enforce_rate_limit("announcement-update", settings.admin_mutation_rate_limit)],
    responses={
        403: {"model": ErrorResponse, "description": "CSRF token is invalid or admin role is required"},
        404: {"model": ErrorResponse, "description": "Announcement was not found"},
        422: {"model": ErrorResponse, "description": "Request payload is invalid"},
    },
)
def update_announcement(
    announcement_id: str,
    payload: AnnouncementUpdateRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    audit = OperationAuditService(db)
    context = extract_request_audit_context(request)
    try:
        _require_admin(current_user)
        result = AnnouncementsService(db).update(
            current_user,
            announcement_id,
            title=payload.title,
            body=payload.body,
            status=payload.status,
            publish_from=payload.publish_from,
            publish_to=payload.publish_to,
        )
    except ApiError as exc:
        audit.log(
            event_type="announcement_management",
            action="update",
            result="failure",
            error_code=exc.code,
            error_detail=summarize_operation_audit_error(exc),
            actor=current_user,
            target_type="announcement",
            target_id=announcement_id,
            context=context,
            metadata={"announcement_id": announcement_id, "status": payload.status, "title": payload.title},
        )
        raise
    except Exception as exc:
        audit.log(
            event_type="announcement_management",
            action="update",
            result="failure",
            error_code="INTERNAL_ERROR",
            error_detail=summarize_operation_audit_error(exc),
            actor=current_user,
            target_type="announcement",
            target_id=announcement_id,
            context=context,
            metadata={"announcement_id": announcement_id, "status": payload.status, "title": payload.title},
        )
        raise

    audit.log(
        event_type="announcement_management",
        action="update",
        result="success",
        actor=current_user,
        target_type="announcement",
        target_id=result["id"],
        context=context,
        metadata={"announcement_id": result["id"], "status": result["status"], "title": result["title"]},
    )
    return result


@router.delete(
    "/announcements/{announcement_id}",
    status_code=204,
    dependencies=[Depends(csrf_protected), enforce_rate_limit("announcement-delete", settings.admin_mutation_rate_limit)],
    responses={
        403: {"model": ErrorResponse, "description": "CSRF token is invalid or admin role is required"},
        404: {"model": ErrorResponse, "description": "Announcement was not found"},
    },
)
def delete_announcement(
    announcement_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    audit = OperationAuditService(db)
    context = extract_request_audit_context(request)
    try:
        _require_admin(current_user)
        result = AnnouncementsService(db).delete(announcement_id)
    except ApiError as exc:
        audit.log(
            event_type="announcement_management",
            action="delete",
            result="failure",
            error_code=exc.code,
            error_detail=summarize_operation_audit_error(exc),
            actor=current_user,
            target_type="announcement",
            target_id=announcement_id,
            context=context,
            metadata={"announcement_id": announcement_id},
        )
        raise
    except Exception as exc:
        audit.log(
            event_type="announcement_management",
            action="delete",
            result="failure",
            error_code="INTERNAL_ERROR",
            error_detail=summarize_operation_audit_error(exc),
            actor=current_user,
            target_type="announcement",
            target_id=announcement_id,
            context=context,
            metadata={"announcement_id": announcement_id},
        )
        raise

    audit.log(
        event_type="announcement_management",
        action="delete",
        result="success",
        actor=current_user,
        target_type="announcement",
        target_id=result["id"],
        context=context,
        metadata={"announcement_id": result["id"], "title": result["title"]},
    )

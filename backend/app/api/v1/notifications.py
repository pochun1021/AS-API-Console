from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.schemas.notifications import (
    NotificationListResponse,
    NotificationReadAllResponse,
    NotificationReadResponse,
)
from app.services.notifications_service import NotificationsService
from db.session import get_db

router = APIRouter()


@router.get("/notifications", response_model=NotificationListResponse)
def list_notifications(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    is_read: bool | None = Query(default=None),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    service = NotificationsService(db)
    return service.list_notifications(current_user=current_user, page=page, page_size=page_size, is_read=is_read)


@router.patch("/notifications/{notification_id}/read", response_model=NotificationReadResponse)
def mark_notification_read(
    notification_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    service = NotificationsService(db)
    try:
        return service.mark_notification_read(current_user=current_user, notification_id=notification_id)
    except Exception:
        db.rollback()
        raise


@router.patch("/notifications/read-all", response_model=NotificationReadAllResponse)
def mark_all_notifications_read(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    service = NotificationsService(db)
    try:
        return service.mark_all_notifications_read(current_user=current_user)
    except Exception:
        db.rollback()
        raise

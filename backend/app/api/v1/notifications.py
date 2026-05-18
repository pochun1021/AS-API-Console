from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.errors import ApiError
from app.schemas.notifications import (
    NotificationListResponse,
    NotificationReadAllResponse,
    NotificationReadResponse,
)
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
    raise ApiError("FEATURE_DISABLED", "notifications are disabled", 410)


@router.patch("/notifications/{notification_id}/read", response_model=NotificationReadResponse)
def mark_notification_read(
    notification_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    raise ApiError("FEATURE_DISABLED", "notifications are disabled", 410)


@router.patch("/notifications/read-all", response_model=NotificationReadAllResponse)
def mark_all_notifications_read(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    raise ApiError("FEATURE_DISABLED", "notifications are disabled", 410)

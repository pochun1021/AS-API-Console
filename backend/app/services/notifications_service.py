from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.errors import ApiError


class NotificationsService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_notifications(self, *, current_user: CurrentUser, page: int, page_size: int, is_read: bool | None) -> dict:
        raise ApiError("FEATURE_DISABLED", "notifications are disabled", 410)

    def mark_notification_read(self, *, current_user: CurrentUser, notification_id: str) -> dict:
        raise ApiError("FEATURE_DISABLED", "notifications are disabled", 410)

    def mark_all_notifications_read(self, *, current_user: CurrentUser) -> dict:
        raise ApiError("FEATURE_DISABLED", "notifications are disabled", 410)

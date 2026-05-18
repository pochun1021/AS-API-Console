import json
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.errors import ApiError
from db.models.notifications import Notification


class NotificationsService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_notifications(self, *, current_user: CurrentUser, page: int, page_size: int, is_read: bool | None) -> dict:
        offset = (page - 1) * page_size
        stmt = select(Notification).where(Notification.sysid == current_user.sysid)
        if is_read is not None:
            stmt = stmt.where(Notification.is_read == is_read)

        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self.session.scalar(total_stmt) or 0)
        items = list(
            self.session.scalars(stmt.order_by(Notification.created_at.desc()).offset(offset).limit(page_size)).all()
        )
        return {
            "items": [self._serialize_item(item) for item in items],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    def mark_notification_read(self, *, current_user: CurrentUser, notification_id: str) -> dict:
        stmt = select(Notification).where(Notification.id == notification_id, Notification.sysid == current_user.sysid)
        notification = self.session.scalar(stmt)
        if notification is None:
            raise ApiError("VALIDATION_ERROR", "notification not found", 404)

        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.now(UTC)
            self.session.add(notification)
            self.session.commit()
        return {"id": notification.id, "is_read": notification.is_read, "read_at": notification.read_at}

    def mark_all_notifications_read(self, *, current_user: CurrentUser) -> dict:
        now = datetime.now(UTC)
        stmt = select(Notification).where(Notification.sysid == current_user.sysid, Notification.is_read.is_(False))
        notifications = list(self.session.scalars(stmt).all())
        for notification in notifications:
            notification.is_read = True
            notification.read_at = now
            self.session.add(notification)
        if notifications:
            self.session.commit()
        return {"updated": len(notifications)}

    def _serialize_item(self, item: Notification) -> dict:
        metadata = None
        if item.metadata_json:
            try:
                metadata = json.loads(item.metadata_json)
            except json.JSONDecodeError:
                metadata = None
        return {
            "id": item.id,
            "type": item.type,
            "title": item.title,
            "message": item.message,
            "is_read": item.is_read,
            "created_at": item.created_at,
            "read_at": item.read_at,
            "metadata": metadata,
        }

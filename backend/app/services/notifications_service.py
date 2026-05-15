import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.errors import ApiError
from db.models.notifications import Notification
from db.repositories import SQLAlchemyUserRepository
from db.repositories.types import AuthIdentity


class NotificationsService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.user_repo = SQLAlchemyUserRepository(session)

    def _ensure_user(self, current_user: CurrentUser):
        return self.user_repo.upsert_from_auth(
            AuthIdentity(
                account=current_user.account,
                name=current_user.name,
                email=current_user.email,
                department=current_user.department,
                sysid=current_user.sysid,
            )
        )

    def list_notifications(self, *, current_user: CurrentUser, page: int, page_size: int, is_read: bool | None) -> dict:
        user = self._ensure_user(current_user)
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        offset = (page - 1) * page_size

        query = self.session.query(Notification).filter(Notification.user_id == user.id)
        if is_read is not None:
            query = query.filter(Notification.is_read == is_read)

        total = query.count()
        items = query.order_by(Notification.created_at.desc()).offset(offset).limit(page_size).all()

        return {
            "items": [self._serialize(item) for item in items],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    def mark_notification_read(self, *, current_user: CurrentUser, notification_id: str) -> dict:
        user = self._ensure_user(current_user)
        item = (
            self.session.query(Notification)
            .filter(Notification.id == notification_id, Notification.user_id == user.id)
            .one_or_none()
        )
        if item is None:
            raise ApiError("VALIDATION_ERROR", "notification not found", 404)
        if not item.is_read:
            item.is_read = True
            item.read_at = datetime.now(UTC)
            self.session.add(item)
            self.session.commit()
        return {"id": item.id, "is_read": item.is_read, "read_at": item.read_at}

    def mark_all_notifications_read(self, *, current_user: CurrentUser) -> dict:
        user = self._ensure_user(current_user)
        now = datetime.now(UTC)
        updated = (
            self.session.query(Notification)
            .filter(Notification.user_id == user.id, Notification.is_read.is_(False))
            .update({"is_read": True, "read_at": now}, synchronize_session=False)
        )
        self.session.commit()
        return {"updated": int(updated)}

    @staticmethod
    def _serialize(item: Notification) -> dict:
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

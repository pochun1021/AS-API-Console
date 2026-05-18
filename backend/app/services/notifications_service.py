import json
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.config import get_settings
from app.core.errors import ApiError
from app.services.crypto_service import CryptoService
from db.models.api_keys import ApiKey
from db.models.applications import ApiKeyApplication
from db.models.notifications import Notification


class NotificationsService:
    def __init__(self, session: Session) -> None:
        self.session = session
        settings = get_settings()
        self.crypto = CryptoService(settings.api_key_encryption_secret)

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

        revealed_plaintext = None
        first_read = not notification.is_read
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.now(UTC)
            self.session.add(notification)
            self.session.commit()
            if notification.type == "api_key_issued":
                revealed_plaintext = self._reveal_once_for_notification(current_user=current_user, notification=notification)
        return {
            "id": notification.id,
            "is_read": notification.is_read,
            "read_at": notification.read_at,
            "revealed": bool(first_read and revealed_plaintext),
            "api_key_plaintext": revealed_plaintext if first_read else None,
        }

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

    def _reveal_once_for_notification(self, *, current_user: CurrentUser, notification: Notification) -> str | None:
        metadata = None
        if notification.metadata_json:
            try:
                metadata = json.loads(notification.metadata_json)
            except json.JSONDecodeError:
                metadata = None
        key_id = metadata.get("key_id") if isinstance(metadata, dict) else None
        application_id = metadata.get("application_id") if isinstance(metadata, dict) else None

        stmt = select(ApiKey).join(ApiKeyApplication, ApiKey.application_id == ApiKeyApplication.id).where(
            ApiKeyApplication.sysid == current_user.sysid
        )
        if key_id:
            stmt = stmt.where(ApiKey.id == key_id)
        elif application_id:
            stmt = stmt.where(ApiKey.application_id == application_id)
        else:
            return None

        key_row = self.session.scalar(stmt)
        if key_row is None or not key_row.key_ciphertext:
            return None
        return self.crypto.decrypt(key_row.key_ciphertext)

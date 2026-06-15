from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.errors import ApiError
from app.core.input_validation import validate_safe_persisted_text
from db.repositories import SQLAlchemyAnnouncementRepository
from db.repositories.types import AnnouncementCreateInput, AnnouncementListFilter, AnnouncementUpdateInput


class AnnouncementsService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = SQLAlchemyAnnouncementRepository(session)

    @staticmethod
    def _serialize(item) -> dict:
        return {
            "id": item.id,
            "title": item.title,
            "body": item.body,
            "status": item.status,
            "publish_from": item.publish_from,
            "publish_to": item.publish_to,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }

    @staticmethod
    def _normalize_payload(
        *,
        title: str,
        body: str,
        status: str,
        publish_from: datetime | None,
        publish_to: datetime | None,
    ) -> dict:
        normalized_title = validate_safe_persisted_text(
            field_name="title",
            value=title,
            required=True,
            allow_empty=False,
        )
        normalized_body = validate_safe_persisted_text(
            field_name="body",
            value=body,
            required=True,
            allow_empty=False,
        )
        if status not in {"active", "inactive"}:
            raise ApiError("VALIDATION_ERROR", "status must be active or inactive", 422)
        if publish_from and publish_to and publish_from > publish_to:
            raise ApiError("VALIDATION_ERROR", "publish_from must be less than or equal to publish_to", 422)
        return {
            "title": normalized_title,
            "body": normalized_body,
            "status": status,
            "publish_from": publish_from,
            "publish_to": publish_to,
        }

    def list(
        self,
        *,
        current_user: CurrentUser,
        scope: str | None,
        status: str | None,
        title: str | None,
        publish_from_from: datetime | None,
        publish_from_to: datetime | None,
        publish_to_from: datetime | None,
        publish_to_to: datetime | None,
        updated_from: datetime | None,
        updated_to: datetime | None,
        sort_by: str,
        sort_dir: str,
        page: int,
        page_size: int,
    ) -> dict:
        active_only = scope != "all"
        if scope not in {None, "all"}:
            raise ApiError("VALIDATION_ERROR", "scope must be all when provided", 422)
        if scope == "all" and current_user.role != "admin":
            raise ApiError("FORBIDDEN", "admin role required", 403)
        if status is not None and status not in {"active", "inactive"}:
            raise ApiError("VALIDATION_ERROR", "status must be active or inactive", 422)
        if sort_by not in {"title", "status", "publish_from", "publish_to", "created_at", "updated_at"}:
            raise ApiError("VALIDATION_ERROR", "unsupported sort_by", 422)
        if sort_dir not in {"asc", "desc"}:
            raise ApiError("VALIDATION_ERROR", "sort_dir must be asc or desc", 422)

        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        offset = (page - 1) * page_size
        items, total = self.repo.list(
            AnnouncementListFilter(
                title=title.strip() if title else None,
                status=status,
                publish_from_from=publish_from_from,
                publish_from_to=publish_from_to,
                publish_to_from=publish_to_from,
                publish_to_to=publish_to_to,
                updated_from=updated_from,
                updated_to=updated_to,
                sort_by=sort_by,
                sort_dir=sort_dir,
            ),
            active_only=active_only,
            now=datetime.now(timezone.utc),
            limit=page_size,
            offset=offset,
        )
        return {
            "items": [self._serialize(item) for item in items],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    def create(
        self,
        current_user: CurrentUser,
        *,
        title: str,
        body: str,
        status: str,
        publish_from: datetime | None,
        publish_to: datetime | None,
    ) -> dict:
        normalized = self._normalize_payload(
            title=title,
            body=body,
            status=status,
            publish_from=publish_from,
            publish_to=publish_to,
        )
        item = self.repo.create(
            AnnouncementCreateInput(
                id=str(uuid4()),
                title=normalized["title"],
                body=normalized["body"],
                status=normalized["status"],
                publish_from=normalized["publish_from"],
                publish_to=normalized["publish_to"],
                created_by=current_user.account,
            )
        )
        self.session.commit()
        return self._serialize(item)

    def update(
        self,
        current_user: CurrentUser,
        announcement_id: str,
        *,
        title: str,
        body: str,
        status: str,
        publish_from: datetime | None,
        publish_to: datetime | None,
    ) -> dict:
        normalized = self._normalize_payload(
            title=title,
            body=body,
            status=status,
            publish_from=publish_from,
            publish_to=publish_to,
        )
        item = self.repo.update(
            announcement_id,
            AnnouncementUpdateInput(
                title=normalized["title"],
                body=normalized["body"],
                status=normalized["status"],
                publish_from=normalized["publish_from"],
                publish_to=normalized["publish_to"],
                updated_by=current_user.account,
            ),
        )
        if item is None:
            raise ApiError("VALIDATION_ERROR", "announcement not found", 404)
        self.session.commit()
        return self._serialize(item)

    def delete(self, announcement_id: str) -> dict:
        item = self.repo.delete(announcement_id)
        if item is None:
            raise ApiError("VALIDATION_ERROR", "announcement not found", 404)
        self.session.commit()
        return {"id": item.id, "title": item.title}

from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.errors import ApiError
from db.repositories import SQLAlchemyWhitelistRepository
from db.repositories.types import WhitelistCreateInput, WhitelistUpdateInput


class WhitelistsService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = SQLAlchemyWhitelistRepository(session)

    def create(self, current_user: CurrentUser, sysid: str, note: str | None) -> dict:
        normalized_sysid = sysid.strip()
        if not normalized_sysid:
            raise ApiError("VALIDATION_ERROR", "sysid is required", 422)

        if self.repo.get_by_sysid(normalized_sysid) is not None:
            raise ApiError("WHITELIST_SYSID_DUPLICATED", "whitelist sysid already exists", 409)

        try:
            item = self.repo.create(
                WhitelistCreateInput(
                    id=str(uuid4()),
                    sysid=normalized_sysid,
                    email=None,
                    created_by=current_user.account,
                    note=note,
                )
            )
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ApiError("WHITELIST_SYSID_DUPLICATED", "whitelist sysid already exists", 409) from exc

        return {
            "id": item.id,
            "sysid": item.sysid,
            "email": item.email,
            "status": item.status,
            "note": item.note,
            "created_by": item.created_by,
            "updated_by": item.updated_by,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }

    def list(self, status: str | None, page: int, page_size: int) -> dict:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        offset = (page - 1) * page_size
        items = self.repo.list(status=status, limit=page_size, offset=offset)

        return {
            "items": [
                {
                    "id": item.id,
                    "sysid": item.sysid,
                    "email": item.email,
                    "status": item.status,
                    "note": item.note,
                    "created_by": item.created_by,
                    "updated_by": item.updated_by,
                    "created_at": item.created_at,
                    "updated_at": item.updated_at,
                }
                for item in items
            ],
            "page": page,
            "page_size": page_size,
            "total": len(items),
        }

    def update(self, current_user: CurrentUser, whitelist_id: str, status: str, note: str | None) -> dict:
        if status not in {"active", "inactive"}:
            raise ApiError("VALIDATION_ERROR", "status must be active or inactive", 422)

        item = self.repo.update_status(
            whitelist_id,
            WhitelistUpdateInput(status=status, updated_by=current_user.account, note=note),
        )
        if item is None:
            raise ApiError("VALIDATION_ERROR", "whitelist item not found", 404)

        self.session.commit()
        return {
            "id": item.id,
            "sysid": item.sysid,
            "email": item.email,
            "status": item.status,
            "note": item.note,
            "created_by": item.created_by,
            "updated_by": item.updated_by,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }

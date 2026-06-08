from datetime import datetime
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.errors import ApiError
from app.core.input_validation import validate_safe_persisted_text
from db.repositories import SQLAlchemyWhitelistRepository
from db.repositories.types import WhitelistCreateInput, WhitelistListFilter, WhitelistUpdateInput


class WhitelistsService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = SQLAlchemyWhitelistRepository(session)

    def create(self, current_user: CurrentUser, sysid: int, account: str, name: str, email: str, note: str | None) -> dict:
        if sysid <= 0:
            raise ApiError("VALIDATION_ERROR", "sysid must be positive integer", 422)
        if not account.strip() or not name.strip() or not email.strip():
            raise ApiError("VALIDATION_ERROR", "account, name, email are required", 422)
        normalized_note = validate_safe_persisted_text(
            field_name="note",
            value=note,
            allow_empty=True,
            restrict_special_chars=True,
            allow_spaces=True,
        )
        if self.repo.get_by_sysid(sysid) is not None:
            raise ApiError("WHITELIST_SYSID_DUPLICATED", "whitelist sysid already exists", 409)

        try:
            item = self.repo.create(
                WhitelistCreateInput(
                    id=str(uuid4()),
                    sysid=sysid,
                    account=account.strip(),
                    name=name.strip(),
                    email=email.strip().lower(),
                    created_by=current_user.account,
                    note=normalized_note,
                )
            )
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ApiError("WHITELIST_SYSID_DUPLICATED", "whitelist sysid already exists", 409) from exc

        return {
            "id": item.id,
            "sysid": item.sysid,
            "account": item.account,
            "name": item.name,
            "email": item.email,
            "status": item.status,
            "note": item.note,
            "created_by": item.created_by,
            "updated_by": item.updated_by,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }

    def list(
        self,
        *,
        status: str | None,
        sysid: int | None,
        account: str | None,
        name: str | None,
        email: str | None,
        created_from: datetime | None,
        created_to: datetime | None,
        updated_from: datetime | None,
        updated_to: datetime | None,
        sort_by: str,
        sort_dir: str,
        page: int,
        page_size: int,
    ) -> dict:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        offset = (page - 1) * page_size
        if status is not None and status not in {"active", "inactive"}:
            raise ApiError("VALIDATION_ERROR", "status must be active or inactive", 422)
        if sort_by not in {"sysid", "account", "name", "email", "status", "created_at", "updated_at"}:
            raise ApiError("VALIDATION_ERROR", "unsupported sort_by", 422)
        if sort_dir not in {"asc", "desc"}:
            raise ApiError("VALIDATION_ERROR", "sort_dir must be asc or desc", 422)

        items, total = self.repo.list(
            WhitelistListFilter(
                status=status,
                sysid=sysid,
                account=account.strip() if account else None,
                name=name.strip() if name else None,
                email=email.strip().lower() if email else None,
                created_from=created_from,
                created_to=created_to,
                updated_from=updated_from,
                updated_to=updated_to,
                sort_by=sort_by,
                sort_dir=sort_dir,
            ),
            limit=page_size,
            offset=offset,
        )

        return {
            "items": [
                {
                    "id": item.id,
                    "sysid": item.sysid,
                    "account": item.account,
                    "name": item.name,
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
            "total": total,
        }

    def update(self, current_user: CurrentUser, whitelist_id: str, status: str, note: str | None) -> dict:
        if status not in {"active", "inactive"}:
            raise ApiError("VALIDATION_ERROR", "status must be active or inactive", 422)
        normalized_note = validate_safe_persisted_text(
            field_name="note",
            value=note,
            allow_empty=True,
            restrict_special_chars=True,
            allow_spaces=True,
        )

        item = self.repo.update_status(
            whitelist_id,
            WhitelistUpdateInput(status=status, updated_by=current_user.account, note=normalized_note),
        )
        if item is None:
            raise ApiError("VALIDATION_ERROR", "whitelist item not found", 404)

        self.session.commit()
        return {
            "id": item.id,
            "sysid": item.sysid,
            "account": item.account,
            "name": item.name,
            "email": item.email,
            "status": item.status,
            "note": item.note,
            "created_by": item.created_by,
            "updated_by": item.updated_by,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }

    def delete(self, whitelist_id: str) -> dict:
        item = self.repo.delete(whitelist_id)
        if item is None:
            raise ApiError("VALIDATION_ERROR", "whitelist item not found", 404)
        self.session.commit()
        return {
            "id": item.id,
            "sysid": item.sysid,
        }

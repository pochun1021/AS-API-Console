from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.errors import ApiError
from app.services.persnl_soap_service import PersnlSoapService, PersnlSoapUnavailableError
from db.models.user_preferences import UserPreference
from db.repositories import SQLAlchemyAdminRepository
from db.repositories.types import AdminListFilter


class UsersService:
    def __init__(self, session: Session, persnl_service: PersnlSoapService | None = None) -> None:
        self.session = session
        self.repo = SQLAlchemyAdminRepository(session)
        self.persnl = persnl_service or PersnlSoapService()

    def search(self, q: str, limit: int = 20) -> dict:
        keyword = q.strip()
        try:
            users = self.persnl.search_by_keyword(keyword, limit=limit)
        except PersnlSoapUnavailableError as exc:
            raise ApiError("SOAP_SERVICE_UNAVAILABLE", "soap service unavailable", 503) from exc
        return {
            "items": [
                {
                    "id": str(user["sysId"]),
                    "sysid": int(user["sysId"]),
                    "account": user["cn"],
                    "name": user["chName"],
                    "email": user["email"],
                    "department": user["instCode"],
                    "role": "user",
                    "status": "active",
                }
                for user in users
            ],
            "total": len(users),
        }

    def list_admins(
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

        admins, total = self.repo.list(
            AdminListFilter(
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
                    "id": str(admin.id),
                    "sysid": int(admin.id),
                    "account": admin.account,
                    "name": admin.name,
                    "email": admin.email,
                    "department": admin.department or "",
                    "role": "admin",
                    "status": admin.status,
                    "created_at": admin.created_at,
                    "updated_at": admin.updated_at,
                }
                for admin in admins
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    def enable_admin(self, current_user: CurrentUser, user_id: int) -> dict:
        user = self.repo.set_status(user_id, status="active", updated_by=current_user.account)
        if user is None:
            raise ApiError("USER_NOT_FOUND", "admin not found", 404)
        self.session.commit()
        return {"id": user.id, "role": "admin", "status": user.status}

    def create_admin(
        self,
        current_user: CurrentUser,
        user_id: int,
        *,
        account: str,
        name: str,
        email: str,
        department: str,
    ) -> dict:
        if self.repo.get_by_id(user_id) is not None:
            raise ApiError("ADMIN_ALREADY_EXISTS", "admin already exists", 409)
        user = self.repo.create(
            admin_id=user_id,
            account=account,
            name=name,
            email=email,
            department=department,
            created_by=current_user.account,
        )
        self.session.commit()
        return {"id": user.id, "role": "admin", "status": user.status}

    def disable_admin(self, current_user: CurrentUser, user_id: int) -> dict:
        user = self.repo.set_status(user_id, status="inactive", updated_by=current_user.account)
        if user is None:
            raise ApiError("USER_NOT_FOUND", "admin not found", 404)
        self.session.commit()
        return {"id": user.id, "role": "admin", "status": user.status}

    def delete_inactive_admin(self, current_user: CurrentUser, user_id: int) -> None:
        user = self.repo.get_by_id(user_id)
        if user is None:
            raise ApiError("USER_NOT_FOUND", "admin not found", 404)
        if user.status != "inactive":
            raise ApiError("VALIDATION_ERROR", "active admin cannot be deleted", 422)
        self.repo.delete(user_id)
        self.session.commit()

    def get_locale_preference(self, current_user: CurrentUser) -> dict:
        preference = self.session.get(UserPreference, current_user.sysid)
        return {"preferred_locale": preference.preferred_locale if preference else None}

    def update_locale_preference(self, current_user: CurrentUser, preferred_locale: str) -> dict:
        if preferred_locale not in {"zh-TW", "en"}:
            raise ApiError("VALIDATION_ERROR", "preferred_locale must be one of: zh-TW, en", 422)

        preference = self.session.get(UserPreference, current_user.sysid)
        now = datetime.now(timezone.utc)
        if preference is None:
            preference = UserPreference(
                sysid=current_user.sysid,
                preferred_locale=preferred_locale,
                created_at=now,
                updated_at=now,
            )
        else:
            preference.preferred_locale = preferred_locale
            preference.updated_at = now
        self.session.add(preference)
        self.session.commit()
        return {"preferred_locale": preference.preferred_locale}

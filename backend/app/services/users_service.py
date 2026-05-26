from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.errors import ApiError
from app.services.persnl_soap_service import PersnlSoapService, PersnlSoapUnavailableError
from db.models.user_preferences import UserPreference
from db.repositories import SQLAlchemyAdminRepository


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

    def list_admins(self, limit: int = 100) -> dict:
        admins = self.repo.list_all(limit=limit)
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
                }
                for admin in admins
            ],
            "total": len(admins),
        }

    def enable_admin(self, current_user: CurrentUser, user_id: int) -> dict:
        user = self.repo.set_status(user_id, status="active", updated_by=current_user.account)
        if user is None:
            raise ApiError("USER_NOT_FOUND", "admin not found", 404)
        self.session.commit()
        return {"id": user.id, "role": "admin", "status": user.status}

    def disable_admin(self, current_user: CurrentUser, user_id: int) -> dict:
        user = self.repo.set_status(user_id, status="inactive", updated_by=current_user.account)
        if user is None:
            raise ApiError("USER_NOT_FOUND", "admin not found", 404)
        self.session.commit()
        return {"id": user.id, "role": "admin", "status": user.status}

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

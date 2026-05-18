from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.errors import ApiError
from db.models.user_preferences import UserPreference
from db.repositories import SQLAlchemyAdminRepository


class UsersService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = SQLAlchemyAdminRepository(session)

    def search(self, q: str, limit: int = 20) -> dict:
        users = self.repo.search(q, limit=limit)
        return {
            "items": [
                {
                    "id": user.id,
                    "sysid": user.sysid,
                    "account": user.account,
                    "name": user.name,
                    "email": user.email,
                    "role": "admin",
                    "status": user.status,
                }
                for user in users
            ],
            "total": len(users),
        }

    def enable_admin(self, user_id: str) -> dict:
        user = self.repo.set_status(user_id, status="active", updated_by="system")
        if user is None:
            raise ApiError("USER_NOT_FOUND", "admin not found", 404)
        self.session.commit()
        return {"id": user.id, "role": "admin", "status": user.status}

    def disable_admin(self, user_id: str) -> dict:
        user = self.repo.set_status(user_id, status="inactive", updated_by="system")
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

from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.errors import ApiError
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
        raise ApiError("FEATURE_DISABLED", "locale preference is disabled", 410)

    def update_locale_preference(self, current_user: CurrentUser, preferred_locale: str) -> dict:
        raise ApiError("FEATURE_DISABLED", "locale preference is disabled", 410)

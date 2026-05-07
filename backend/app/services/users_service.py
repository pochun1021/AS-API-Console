from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.errors import ApiError
from db.repositories import SQLAlchemyUserRepository
from db.repositories.types import AuthIdentity


class UsersService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = SQLAlchemyUserRepository(session)

    def search(self, q: str, limit: int = 20) -> dict:
        users = self.repo.search(q, limit=limit)
        return {
            "items": [
                {
                    "id": user.id,
                    "sysid": user.id,
                    "account": user.account,
                    "name": user.name,
                    "email": user.email,
                    "role": user.role,
                    "status": user.status,
                }
                for user in users
            ],
            "total": len(users),
        }

    def enable_admin(self, user_id: str) -> dict:
        user = self.repo.update_role(user_id, "admin")
        if user is None:
            raise ApiError("USER_NOT_FOUND", "user not found", 404)
        user = self.repo.update_status(user_id, "active")
        if user is None:
            raise ApiError("USER_NOT_FOUND", "user not found", 404)
        self.session.commit()
        return {"id": user.id, "role": user.role, "status": user.status}

    def disable_admin(self, user_id: str) -> dict:
        user = self.repo.update_status(user_id, "inactive")
        if user is None:
            raise ApiError("USER_NOT_FOUND", "user not found", 404)
        self.session.commit()
        return {"id": user.id, "role": user.role, "status": user.status}

    def get_locale_preference(self, current_user: CurrentUser) -> dict:
        user = self.repo.get_by_account(current_user.account)
        if user is None:
            user = self.repo.upsert_from_auth(
                AuthIdentity(
                    account=current_user.account,
                    name=current_user.name,
                    email=current_user.email,
                    department=current_user.department,
                    sysid=current_user.sysid,
                )
            )
            self.session.commit()
        return {"preferred_locale": user.preferred_locale}

    def update_locale_preference(self, current_user: CurrentUser, preferred_locale: str) -> dict:
        if preferred_locale not in {"zh-TW", "en"}:
            raise ApiError("VALIDATION_ERROR", "preferred_locale must be one of: zh-TW, en", 400)

        user = self.repo.get_by_account(current_user.account)
        if user is None:
            user = self.repo.upsert_from_auth(
                AuthIdentity(
                    account=current_user.account,
                    name=current_user.name,
                    email=current_user.email,
                    department=current_user.department,
                    sysid=current_user.sysid,
                )
            )

        updated = self.repo.update_preferred_locale(user.id, preferred_locale)
        if updated is None:
            raise ApiError("USER_NOT_FOUND", "user not found", 404)
        self.session.commit()
        return {"preferred_locale": updated.preferred_locale}

from sqlalchemy.orm import Session

from app.core.errors import ApiError
from db.repositories import SQLAlchemyUserRepository


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

    def grant_admin(self, user_id: str) -> dict:
        user = self.repo.update_role(user_id, "admin")
        if user is None:
            raise ApiError("USER_NOT_FOUND", "user not found", 404)
        self.session.commit()
        return {"id": user.id, "role": user.role}

    def revoke_admin(self, user_id: str) -> dict:
        user = self.repo.update_role(user_id, "user")
        if user is None:
            raise ApiError("USER_NOT_FOUND", "user not found", 404)
        self.session.commit()
        return {"id": user.id, "role": user.role}

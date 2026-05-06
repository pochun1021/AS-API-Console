from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.errors import ApiError
from app.schemas.users import UserListResponse, UserRoleMutationResponse
from app.services.users_service import UsersService
from db.session import get_db

router = APIRouter()


def _require_admin(current_user: CurrentUser) -> None:
    if current_user.role != "admin":
        raise ApiError("VALIDATION_ERROR", "admin role required", 403)


@router.get("/users", response_model=UserListResponse)
def list_users(
    q: str = Query(default=""),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_admin(current_user)
    service = UsersService(db)
    return service.search(q=q)


@router.post("/users/{user_id}/grant-admin", response_model=UserRoleMutationResponse)
def grant_admin(
    user_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_admin(current_user)
    service = UsersService(db)
    return service.grant_admin(user_id)


@router.post("/users/{user_id}/revoke-admin", response_model=UserRoleMutationResponse)
def revoke_admin(
    user_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_admin(current_user)
    service = UsersService(db)
    return service.revoke_admin(user_id)

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


@router.post("/admins/{user_id}/enable", response_model=UserRoleMutationResponse)
def enable_admin(
    user_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_admin(current_user)
    service = UsersService(db)
    return service.enable_admin(user_id)


@router.post("/admins/{user_id}/disable", response_model=UserRoleMutationResponse)
def disable_admin(
    user_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_admin(current_user)
    service = UsersService(db)
    return service.disable_admin(user_id)

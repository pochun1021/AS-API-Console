from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.errors import ApiError
from app.schemas.whitelists import (
    WhitelistCreateRequest,
    WhitelistItemResponse,
    WhitelistListResponse,
    WhitelistUpdateRequest,
)
from app.services.whitelists_service import WhitelistsService
from db.session import get_db

router = APIRouter()


def _require_admin(current_user: CurrentUser) -> None:
    if current_user.role != "admin":
        raise ApiError("VALIDATION_ERROR", "admin role required", 403)


@router.post("/whitelists", response_model=WhitelistItemResponse, status_code=201)
def create_whitelist(
    payload: WhitelistCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_admin(current_user)
    service = WhitelistsService(db)
    return service.create(current_user, payload.sysid, payload.note)


@router.get("/whitelists", response_model=WhitelistListResponse)
def list_whitelists(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_admin(current_user)
    service = WhitelistsService(db)
    return service.list(status=status, page=page, page_size=page_size)


@router.patch("/whitelists/{whitelist_id}", response_model=WhitelistItemResponse)
def update_whitelist(
    whitelist_id: str,
    payload: WhitelistUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_admin(current_user)
    service = WhitelistsService(db)
    return service.update(current_user, whitelist_id, payload.status, payload.note)

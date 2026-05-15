from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.schemas.api_keys import (
    ApiKeyDetailResponse,
    ApiKeyAliasUpdateRequest,
    ApiKeyListResponse,
    ApiKeyRevealResponse,
    ApiKeyUserStatisticsResponse,
    ApplicationCreateRequest,
    ApplicationCreateResponse,
    RevokeResponse,
)
from app.services.api_keys_service import ApiKeysService
from db.session import get_db

router = APIRouter()


@router.post("/api-keys/applications", response_model=ApplicationCreateResponse, status_code=201)
def create_application(
    payload: ApplicationCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    service = ApiKeysService(db)
    try:
        return service.create_application(
            current_user=current_user,
            application_date=payload.application_date,
            duration_months=payload.duration_months,
            purpose=payload.purpose,
        )
    except Exception:
        db.rollback()
        raise


@router.get("/api-keys", response_model=ApiKeyListResponse)
def list_api_keys(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    owner_account: str | None = Query(default=None),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    service = ApiKeysService(db)
    return service.list_keys(
        current_user=current_user,
        page=page,
        page_size=page_size,
        status=status,
        owner_account=owner_account,
        from_date=from_date,
        to_date=to_date,
    )


@router.get("/api-keys/statistics/users", response_model=ApiKeyUserStatisticsResponse)
def list_api_key_user_statistics(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None),
    scope: str = Query(default="all"),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    sort_by: str = Query(default="total_applications"),
    sort_dir: str = Query(default="desc"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    service = ApiKeysService(db)
    return service.list_user_statistics(
        current_user=current_user,
        page=page,
        page_size=page_size,
        q=q,
        scope=scope,
        from_date=from_date,
        to_date=to_date,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.get("/api-keys/{key_id}", response_model=ApiKeyDetailResponse)
def get_api_key_detail(
    key_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    service = ApiKeysService(db)
    return service.get_key_detail(current_user=current_user, key_id=key_id)


@router.post("/api-keys/{key_id}/revoke", response_model=RevokeResponse)
def revoke_api_key(
    key_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    service = ApiKeysService(db)
    try:
        return service.revoke_key(current_user=current_user, key_id=key_id)
    except Exception:
        db.rollback()
        raise


@router.post("/api-keys/{key_id}/reveal", response_model=ApiKeyRevealResponse)
def reveal_api_key(
    key_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    service = ApiKeysService(db)
    return service.reveal_key_plaintext(current_user=current_user, key_id=key_id)


@router.patch("/api-keys/{key_id}", response_model=ApiKeyDetailResponse)
def update_api_key_alias(
    key_id: str,
    payload: ApiKeyAliasUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    service = ApiKeysService(db)
    try:
        return service.update_key_alias(current_user=current_user, key_id=key_id, key_alias=payload.key_alias)
    except Exception:
        db.rollback()
        raise

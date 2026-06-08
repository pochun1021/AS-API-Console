from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.security import validate_date_window, validate_search_keyword
from app.schemas.auth_audit_logs import AuthAuditLogListResponse
from app.schemas.common import ErrorResponse
from app.services.auth_audit_query_service import AuthAuditQueryService
from db.session import get_db

router = APIRouter()


@router.get(
    "/auth-audit-logs",
    response_model=AuthAuditLogListResponse,
    responses={
        403: {"model": ErrorResponse, "description": "Admin role is required"},
        422: {"model": ErrorResponse, "description": "Query parameters are invalid"},
    },
)
def list_auth_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    provider: str | None = Query(default=None),
    result: str | None = Query(default=None),
    account: str | None = Query(default=None),
    sysid: int | None = Query(default=None),
    role: str | None = Query(default=None),
    error_code: str | None = Query(default=None),
    request_id: str | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    service = AuthAuditQueryService(db)
    validate_date_window(from_date, to_date)
    validate_search_keyword(provider)
    validate_search_keyword(account)
    validate_search_keyword(role)
    validate_search_keyword(error_code)
    validate_search_keyword(request_id)
    return service.list_logs(
        current_user=current_user,
        page=page,
        page_size=page_size,
        from_date=from_date,
        to_date=to_date,
        provider=provider,
        result=result,
        account=account,
        sysid=sysid,
        role=role,
        error_code=error_code,
        request_id=request_id,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

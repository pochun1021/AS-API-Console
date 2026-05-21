from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.security import validate_date_window
from app.schemas.auth_audit_logs import AuthAuditLogListResponse
from app.services.auth_audit_query_service import AuthAuditQueryService
from db.session import get_db

router = APIRouter()


@router.get("/auth-audit-logs", response_model=AuthAuditLogListResponse)
def list_auth_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    provider: str | None = Query(default=None),
    result: str | None = Query(default=None),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    service = AuthAuditQueryService(db)
    validate_date_window(from_date, to_date)
    return service.list_logs(
        current_user=current_user,
        page=page,
        page_size=page_size,
        from_date=from_date,
        to_date=to_date,
        provider=provider,
        result=result,
    )

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.security import validate_date_window
from app.schemas.operation_audit_logs import OperationAuditLogListResponse
from app.services.operation_audit_query_service import OperationAuditQueryService
from db.session import get_db

router = APIRouter()


@router.get("/operation-audit-logs", response_model=OperationAuditLogListResponse)
def list_operation_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    event_type: str | None = Query(default=None),
    result: str | None = Query(default=None),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    service = OperationAuditQueryService(db)
    validate_date_window(from_date, to_date)
    return service.list_logs(
        current_user=current_user,
        page=page,
        page_size=page_size,
        from_date=from_date,
        to_date=to_date,
        event_type=event_type,
        result=result,
    )

from datetime import date

from fastapi import APIRouter, Depends, Query

from app.core.auth import CurrentUser, get_current_user
from app.core.security import validate_date_window, validate_search_keyword
from app.schemas.common import ErrorResponse
from app.schemas.scheduler_logs import SchedulerLogListResponse
from app.services.scheduler_log_query_service import SchedulerLogQueryService

router = APIRouter()


@router.get(
    "/scheduler-logs",
    response_model=SchedulerLogListResponse,
    responses={
        403: {"model": ErrorResponse, "description": "Admin role is required"},
        422: {"model": ErrorResponse, "description": "Query parameters are invalid"},
    },
)
def list_scheduler_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    job: str | None = Query(default=None),
    file_mode: str = Query(default="date"),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    level: str | None = Query(default=None),
    keyword: str | None = Query(default=None, alias="q"),
    sort_dir: str = Query(default="desc"),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    if file_mode == "date":
        validate_date_window(from_date, to_date)
    validate_search_keyword(job)
    validate_search_keyword(file_mode)
    validate_search_keyword(level)
    validate_search_keyword(keyword)
    service = SchedulerLogQueryService()
    return service.list_logs(
        current_user=current_user,
        page=page,
        page_size=page_size,
        job=job,
        file_mode=file_mode,
        from_date=from_date,
        to_date=to_date,
        level=level,
        keyword=keyword,
        sort_dir=sort_dir,
    )

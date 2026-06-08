from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.errors import ApiError
from db.models.operation_audit_logs import OperationAuditLog


class OperationAuditQueryService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_logs(
        self,
        *,
        current_user: CurrentUser,
        page: int,
        page_size: int,
        from_date: date | None,
        to_date: date | None,
        event_type: str | None,
        action: str | None,
        result: str | None,
        actor_account: str | None,
        target_type: str | None,
        target_id: str | None,
        error_code: str | None,
        sort_by: str,
        sort_dir: str,
    ) -> dict:
        if current_user.role != "admin":
            raise ApiError("FORBIDDEN", "admin role required", 403)
        if result is not None and result not in {"success", "failure"}:
            raise ApiError("VALIDATION_ERROR", "result must be success or failure", 422)
        allowed_sort_by = {
            "created_at",
            "event_type",
            "action",
            "result",
            "actor_account",
            "target_type",
            "target_id",
            "error_code",
            "request_id",
        }
        if sort_by not in allowed_sort_by:
            raise ApiError("VALIDATION_ERROR", "sort_by is invalid", 422)
        if sort_dir not in {"asc", "desc"}:
            raise ApiError("VALIDATION_ERROR", "sort_dir must be asc or desc", 422)

        if from_date is None and to_date is None:
            to_date = datetime.now(UTC).date()
            from_date = to_date - timedelta(days=6)
        elif from_date is None:
            from_date = to_date
        elif to_date is None:
            to_date = from_date

        if from_date > to_date:
            raise ApiError("VALIDATION_ERROR", "from must be earlier than or equal to to", 422)

        from_dt = datetime.combine(from_date, time.min, tzinfo=UTC)
        to_dt = datetime.combine(to_date, time.max, tzinfo=UTC)

        stmt = select(OperationAuditLog).where(
            OperationAuditLog.created_at >= from_dt,
            OperationAuditLog.created_at <= to_dt,
        )
        if event_type:
            stmt = stmt.where(OperationAuditLog.event_type == event_type)
        if action:
            stmt = stmt.where(OperationAuditLog.action.ilike(f"%{action.strip()}%"))
        if result:
            stmt = stmt.where(OperationAuditLog.result == result)
        if actor_account:
            stmt = stmt.where(OperationAuditLog.actor_account.ilike(f"%{actor_account.strip()}%"))
        if target_type:
            stmt = stmt.where(OperationAuditLog.target_type == target_type)
        if target_id:
            stmt = stmt.where(OperationAuditLog.target_id.ilike(f"%{target_id.strip()}%"))
        if error_code:
            stmt = stmt.where(OperationAuditLog.error_code.ilike(f"%{error_code.strip()}%"))

        sort_expressions = {
            "created_at": OperationAuditLog.created_at,
            "event_type": OperationAuditLog.event_type,
            "action": OperationAuditLog.action,
            "result": OperationAuditLog.result,
            "actor_account": OperationAuditLog.actor_account,
            "target_type": OperationAuditLog.target_type,
            "target_id": OperationAuditLog.target_id,
            "error_code": OperationAuditLog.error_code,
            "request_id": OperationAuditLog.request_id,
        }
        sort_expr = sort_expressions[sort_by]
        order_expr = asc(sort_expr) if sort_dir == "asc" else desc(sort_expr)

        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self.session.scalar(total_stmt) or 0)

        rows = list(
            self.session.scalars(
                stmt.order_by(order_expr, OperationAuditLog.id.asc()).offset((page - 1) * page_size).limit(page_size)
            ).all()
        )
        return {
            "items": [
                {
                    "id": row.id,
                    "created_at": row.created_at,
                    "event_type": row.event_type,
                    "action": row.action,
                    "result": row.result,
                    "actor_account": row.actor_account,
                    "target_type": row.target_type,
                    "target_id": row.target_id,
                    "error_code": row.error_code,
                    "error_detail": row.error_detail,
                    "request_id": row.request_id,
                }
                for row in rows
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

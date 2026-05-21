from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.errors import ApiError
from db.models.auth_audit_logs import AuthAuditLog


class AuthAuditQueryService:
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
        provider: str | None,
        result: str | None,
    ) -> dict:
        if current_user.role != "admin":
            raise ApiError("FORBIDDEN", "admin role required", 403)
        if result is not None and result not in {"success", "failure"}:
            raise ApiError("VALIDATION_ERROR", "result must be success or failure", 422)

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

        stmt = select(AuthAuditLog).where(
            AuthAuditLog.created_at >= from_dt,
            AuthAuditLog.created_at <= to_dt,
        )
        if provider:
            stmt = stmt.where(AuthAuditLog.provider == provider)
        if result:
            stmt = stmt.where(AuthAuditLog.result == result)

        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self.session.scalar(total_stmt) or 0)
        rows = list(
            self.session.scalars(stmt.order_by(AuthAuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
        )
        return {
            "items": [
                {
                    "id": row.id,
                    "created_at": row.created_at,
                    "provider": row.provider,
                    "result": row.result,
                    "account": row.account,
                    "sysid": row.sysid,
                    "role": row.role,
                    "error_code": row.error_code,
                    "request_id": row.request_id,
                }
                for row in rows
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

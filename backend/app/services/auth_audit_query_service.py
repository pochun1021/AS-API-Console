from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import asc, desc, func, select
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
        account: str | None,
        sysid: int | None,
        role: str | None,
        error_code: str | None,
        request_id: str | None,
        sort_by: str,
        sort_dir: str,
    ) -> dict:
        if current_user.role != "admin":
            raise ApiError("FORBIDDEN", "admin role required", 403)
        if result is not None and result not in {"success", "failure"}:
            raise ApiError("VALIDATION_ERROR", "result must be success or failure", 422)
        allowed_sort_by = {
            "created_at",
            "provider",
            "result",
            "account",
            "sysid",
            "role",
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

        stmt = select(AuthAuditLog).where(
            AuthAuditLog.created_at >= from_dt,
            AuthAuditLog.created_at <= to_dt,
        )
        if provider:
            stmt = stmt.where(AuthAuditLog.provider == provider)
        if result:
            stmt = stmt.where(AuthAuditLog.result == result)
        if account:
            stmt = stmt.where(AuthAuditLog.account.ilike(f"%{account.strip()}%"))
        if sysid is not None:
            stmt = stmt.where(AuthAuditLog.sysid == sysid)
        if role:
            stmt = stmt.where(AuthAuditLog.role == role)
        if error_code:
            stmt = stmt.where(AuthAuditLog.error_code.ilike(f"%{error_code.strip()}%"))
        if request_id:
            stmt = stmt.where(AuthAuditLog.request_id.ilike(f"%{request_id.strip()}%"))

        sort_expressions = {
            "created_at": AuthAuditLog.created_at,
            "provider": AuthAuditLog.provider,
            "result": AuthAuditLog.result,
            "account": AuthAuditLog.account,
            "sysid": AuthAuditLog.sysid,
            "role": AuthAuditLog.role,
            "error_code": AuthAuditLog.error_code,
            "request_id": AuthAuditLog.request_id,
        }
        sort_expr = sort_expressions[sort_by]
        order_expr = asc(sort_expr) if sort_dir == "asc" else desc(sort_expr)

        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self.session.scalar(total_stmt) or 0)
        rows = list(
            self.session.scalars(stmt.order_by(order_expr, AuthAuditLog.id.asc()).offset((page - 1) * page_size).limit(page_size)).all()
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

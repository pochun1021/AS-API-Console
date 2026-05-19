from sqlalchemy.orm import Session

from db.models.auth_audit_logs import AuthAuditLog


class AuthAuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def log(
        self,
        *,
        provider: str,
        request_id: str,
        result: str,
        error_code: str | None = None,
        account: str | None = None,
        name: str | None = None,
        email: str | None = None,
        department: str | None = None,
        sysid: int | None = None,
        role: str | None = None,
        detail: str | None = None,
    ) -> None:
        row = AuthAuditLog(
            provider=provider,
            request_id=request_id,
            result=result,
            error_code=error_code,
            account=account,
            name=name,
            email=email.lower() if email else None,
            department=department,
            sysid=sysid,
            role=role,
            detail=detail,
        )
        self.db.add(row)
        self.db.commit()

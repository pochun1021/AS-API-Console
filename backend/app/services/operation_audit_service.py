import json
import logging
from dataclasses import dataclass
from uuid import uuid4

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from db.models.operation_audit_logs import OperationAuditLog

ALLOWED_METADATA_KEYS = {
    "application_id",
    "budget_duration",
    "budget_max_budget",
    "deactivated_count",
    "fetched_count",
    "inserted_count",
    "key_id",
    "note",
    "rate_limit_rpm",
    "rate_limit_tpm",
    "whitelist_id",
    "target_admin_id",
    "status",
    "duration_months",
    "is_proxy_submission",
    "provider_request_id",
    "provider_operation_id",
    "unchanged_count",
    "updated_count",
}


@dataclass(slots=True)
class RequestAuditContext:
    request_id: str
    source_ip: str | None
    user_agent: str | None


def extract_request_audit_context(request: Request) -> RequestAuditContext:
    request_id = request.headers.get("x-request-id") or str(uuid4())
    forwarded_for = request.headers.get("x-forwarded-for")
    source_ip = None
    if forwarded_for:
        source_ip = forwarded_for.split(",")[0].strip()
    elif request.client is not None:
        source_ip = request.client.host
    user_agent = request.headers.get("user-agent")
    return RequestAuditContext(request_id=request_id, source_ip=source_ip, user_agent=user_agent)


class OperationAuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _sanitize_metadata(self, metadata: dict | None) -> dict | None:
        if not metadata:
            return None
        sanitized = {
            key: value
            for key, value in metadata.items()
            if key in ALLOWED_METADATA_KEYS and value is not None
        }
        return sanitized or None

    def log(
        self,
        *,
        event_type: str,
        action: str,
        result: str,
        target_type: str,
        context: RequestAuditContext,
        actor: CurrentUser | None = None,
        error_code: str | None = None,
        target_id: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        sanitized_metadata = self._sanitize_metadata(metadata)
        metadata_json = json.dumps(sanitized_metadata, ensure_ascii=False) if sanitized_metadata else None
        row = OperationAuditLog(
            event_type=event_type,
            action=action,
            result=result,
            error_code=error_code,
            actor_sysid=actor.sysid if actor else None,
            actor_account=actor.account if actor else None,
            actor_role=actor.role if actor else None,
            target_type=target_type,
            target_id=target_id,
            request_id=context.request_id,
            source_ip=context.source_ip,
            user_agent=context.user_agent,
            metadata_json=metadata_json,
        )
        try:
            self.db.add(row)
            self.db.commit()
        except Exception:  # noqa: BLE001
            # Keep API behavior unchanged when audit persistence fails.
            self.db.rollback()
            logging.exception("failed to write operation audit log")

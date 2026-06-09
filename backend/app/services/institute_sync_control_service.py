from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import ceil

from sqlalchemy import or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from db.models.institute_sync_control import InstituteSyncControl

CONTROL_ROW_ID = 1
SUCCESS_COOLDOWN = timedelta(minutes=15)
FAILURE_COOLDOWN = timedelta(minutes=1)


@dataclass(slots=True)
class InstituteSyncStatus:
    status: str
    retry_after_seconds: int
    next_allowed_at: datetime | None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _retry_after_seconds(next_allowed_at: datetime, now: datetime) -> int:
    return max(0, ceil((next_allowed_at - now).total_seconds()))


class InstituteSyncControlService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _ensure_control_row(self) -> InstituteSyncControl:
        row = self.session.get(InstituteSyncControl, CONTROL_ROW_ID)
        if row is not None:
            return row

        now = _utcnow()
        row = InstituteSyncControl(
            id=CONTROL_ROW_ID,
            status="idle",
            created_at=now,
            updated_at=now,
        )
        self.session.add(row)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            row = self.session.get(InstituteSyncControl, CONTROL_ROW_ID)
            if row is None:
                raise
        return row

    def get_status(self) -> InstituteSyncStatus:
        row = self._ensure_control_row()
        now = _utcnow()
        cooldown_until = _as_utc(row.cooldown_until)
        if row.status == "idle" and cooldown_until and cooldown_until > now:
            return InstituteSyncStatus(
                status=row.status,
                retry_after_seconds=_retry_after_seconds(cooldown_until, now),
                next_allowed_at=cooldown_until,
            )
        return InstituteSyncStatus(status=row.status, retry_after_seconds=0, next_allowed_at=None)

    def acquire(self) -> None:
        self._ensure_control_row()
        now = _utcnow()
        updated = self.session.execute(
            update(InstituteSyncControl)
            .where(
                InstituteSyncControl.id == CONTROL_ROW_ID,
                InstituteSyncControl.status == "idle",
                or_(
                    InstituteSyncControl.cooldown_until.is_(None),
                    InstituteSyncControl.cooldown_until <= now,
                ),
            )
            .values(
                status="running",
                last_started_at=now,
                updated_at=now,
            )
        )
        if updated.rowcount == 1:
            self.session.commit()
            return

        self.session.rollback()
        status = self.get_status()
        if status.status == "running":
            raise ApiError("INSTITUTE_SYNC_IN_PROGRESS", "institute sync already in progress", 429)
        if status.retry_after_seconds > 0 and status.next_allowed_at is not None:
            raise ApiError(
                "INSTITUTE_SYNC_COOLDOWN",
                "institute sync is cooling down",
                429,
                extra={
                    "retry_after_seconds": status.retry_after_seconds,
                    "next_allowed_at": status.next_allowed_at.isoformat(),
                },
                headers={"Retry-After": str(status.retry_after_seconds)},
            )
        raise ApiError("INSTITUTE_SYNC_IN_PROGRESS", "institute sync state changed, retry later", 429)

    def finish(self, *, result_code: str, success: bool) -> InstituteSyncStatus:
        cooldown = SUCCESS_COOLDOWN if success else FAILURE_COOLDOWN
        now = _utcnow()
        next_allowed_at = now + cooldown
        self.session.execute(
            update(InstituteSyncControl)
            .where(InstituteSyncControl.id == CONTROL_ROW_ID)
            .values(
                status="idle",
                last_result=result_code,
                last_finished_at=now,
                cooldown_until=next_allowed_at,
                updated_at=now,
            )
        )
        self.session.commit()
        return InstituteSyncStatus(
            status="idle",
            retry_after_seconds=_retry_after_seconds(next_allowed_at, now),
            next_allowed_at=next_allowed_at,
        )

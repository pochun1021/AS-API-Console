from __future__ import annotations

import argparse
import logging
import os
from asyncio import run as run_async
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
LOG_TZ = ZoneInfo("Asia/Taipei")
LOG_ROOT = Path(os.getenv("SCHEDULER_LOG_ROOT", "/home/app/log"))
LOG_DIR = LOG_ROOT / "send_expiration_reminders"
LOGGER_NAME = "send_expiration_reminders"
REMINDER_DAYS = (30, 14, 7, 3, 1)
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings
from app.services.mail_service import MailService
from db import models  # noqa: F401
from db.models.api_key_expiration_notices import ApiKeyExpirationNotice
from db.models.api_keys import ApiKey
from db.models.applications import ApiKeyApplication
from db.session import SessionLocal


@dataclass(slots=True)
class ReminderCandidate:
    key_id: str
    application_id: str
    owner_name: str
    email: str
    expires_at: datetime
    notice_days_before: int


class TaipeiDateFormatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt = datetime.fromtimestamp(record.created, tz=LOG_TZ)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.isoformat(timespec="seconds")


def _build_logger() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{datetime.now(LOG_TZ).strftime('%Y-%m-%d')}.log"
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    formatter = TaipeiDateFormatter("[%(asctime)s] level=%(levelname)s %(message)s")
    file_handler = logging.FileHandler(LOG_DIR / filename, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send API key expiration reminders for keys expiring in 30, 14, 7, 3, or 1 days."
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Maximum rows to process per batch (default: 1000).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show number of rows that would be processed without sending emails.",
    )
    return parser.parse_args()


def _target_window(now: datetime, notice_days_before: int) -> tuple[datetime, datetime]:
    target_day = (now + timedelta(days=notice_days_before)).date()
    start = datetime(target_day.year, target_day.month, target_day.day, tzinfo=UTC)
    end = start + timedelta(days=1)
    return start, end


def _candidate_stmt(*, now: datetime, notice_days_before: int, limit: int):
    window_start, window_end = _target_window(now, notice_days_before)
    sent_exists = (
        select(ApiKeyExpirationNotice.id)
        .where(
            ApiKeyExpirationNotice.key_id == ApiKey.id,
            ApiKeyExpirationNotice.expires_at_snapshot == ApiKeyApplication.expires_at,
            ApiKeyExpirationNotice.success_notice_days_before == notice_days_before,
        )
        .exists()
    )
    return (
        select(ApiKey, ApiKeyApplication)
        .join(ApiKeyApplication, ApiKey.application_id == ApiKeyApplication.id)
        .where(ApiKey.status == "active")
        .where(ApiKeyApplication.expires_at >= window_start)
        .where(ApiKeyApplication.expires_at < window_end)
        .where(~sent_exists)
        .order_by(ApiKeyApplication.expires_at.asc(), ApiKey.id.asc())
        .limit(limit)
    )


def _collect_candidates(*, now: datetime, batch_size: int) -> list[ReminderCandidate]:
    candidates: list[ReminderCandidate] = []
    with SessionLocal() as session:
        for notice_days_before in REMINDER_DAYS:
            remaining = batch_size - len(candidates)
            if remaining <= 0:
                break
            rows = session.execute(
                _candidate_stmt(now=now, notice_days_before=notice_days_before, limit=remaining)
            ).all()
            candidates.extend(
                ReminderCandidate(
                    key_id=row.ApiKey.id,
                    application_id=row.ApiKeyApplication.id,
                    owner_name=row.ApiKeyApplication.name,
                    email=row.ApiKeyApplication.email,
                    expires_at=row.ApiKeyApplication.expires_at,
                    notice_days_before=notice_days_before,
                )
                for row in rows
            )
    return candidates


def _record_failure(
    *,
    session,
    candidate: ReminderCandidate,
    error_message: str,
) -> None:
    session.add(
        ApiKeyExpirationNotice(
            id=str(uuid4()),
            key_id=candidate.key_id,
            application_id=candidate.application_id,
            expires_at_snapshot=candidate.expires_at,
            notice_days_before=candidate.notice_days_before,
            status="failed",
            sent_at=None,
            error_message=error_message,
            success_notice_days_before=None,
        )
    )


def _send_candidate_notice(*, candidate: ReminderCandidate, logger: logging.Logger) -> bool:
    mail_service = MailService()
    settings = get_settings()
    with SessionLocal() as session, session.begin():
        locked = session.execute(
            select(ApiKey, ApiKeyApplication)
            .join(ApiKeyApplication, ApiKey.application_id == ApiKeyApplication.id)
            .where(ApiKey.id == candidate.key_id)
            .with_for_update()
        ).one_or_none()
        if locked is None:
            return False

        key = locked.ApiKey
        app = locked.ApiKeyApplication
        if key.status != "active":
            return False
        if app.expires_at != candidate.expires_at:
            return False

        sent_exists = session.execute(
            select(ApiKeyExpirationNotice.id).where(
                ApiKeyExpirationNotice.key_id == candidate.key_id,
                ApiKeyExpirationNotice.expires_at_snapshot == candidate.expires_at,
                ApiKeyExpirationNotice.success_notice_days_before == candidate.notice_days_before,
            )
        ).first()
        if sent_exists is not None:
            return False

        try:
            run_async(
                mail_service.send_key_expiration_notice(
                    to_email=app.email,
                    owner_name=app.name,
                    days_before=candidate.notice_days_before,
                    expires_at=app.expires_at,
                    app_domain=settings.app_domain,
                )
            )
            sent_at = datetime.now(UTC)
            session.add(
                ApiKeyExpirationNotice(
                    id=str(uuid4()),
                    key_id=key.id,
                    application_id=app.id,
                    expires_at_snapshot=app.expires_at,
                    notice_days_before=candidate.notice_days_before,
                    status="sent",
                    sent_at=sent_at,
                    error_message=None,
                    success_notice_days_before=candidate.notice_days_before,
                )
            )
            if key.expiration_notice_sent_at is None:
                key.expiration_notice_sent_at = sent_at
                session.add(key)
            return True
        except Exception as exc:  # noqa: BLE001
            _record_failure(session=session, candidate=candidate, error_message=str(exc))
            logger.exception(
                "event=expiration_reminder_send_failed key_id=%s application_id=%s expires_at=%s notice_days_before=%s email=%s",
                candidate.key_id,
                candidate.application_id,
                candidate.expires_at.isoformat(),
                candidate.notice_days_before,
                candidate.email,
            )
            return False


def run_once(*, batch_size: int, dry_run: bool, logger: logging.Logger) -> tuple[int, int]:
    now = datetime.now(UTC)
    candidates = _collect_candidates(now=now, batch_size=batch_size)
    if dry_run:
        return len(candidates), 0

    success = 0
    for candidate in candidates:
        try:
            if _send_candidate_notice(candidate=candidate, logger=logger):
                success += 1
        except IntegrityError:
            logger.info(
                "event=expiration_reminder_duplicate_skip key_id=%s application_id=%s expires_at=%s notice_days_before=%s",
                candidate.key_id,
                candidate.application_id,
                candidate.expires_at.isoformat(),
                candidate.notice_days_before,
            )
    return len(candidates), success


def main() -> None:
    args = parse_args()
    logger = _build_logger()
    mode = "dry-run" if args.dry_run else "send"
    try:
        processed, success = run_once(batch_size=args.batch_size, dry_run=args.dry_run, logger=logger)
    except Exception:
        logger.exception(
            "event=expiration_reminder mode=%s batch_size=%s dry_run=%s status=failed",
            mode,
            args.batch_size,
            args.dry_run,
        )
        raise SystemExit(1)

    message = (
        f"expiration-reminder-{mode} processed_count={processed} "
        f"sent_count={success} batch_size={args.batch_size}"
    )
    print(message)
    logger.info(
        "event=expiration_reminder mode=%s processed_count=%s sent_count=%s batch_size=%s dry_run=%s status=success",
        mode,
        processed,
        success,
        args.batch_size,
        args.dry_run,
    )


if __name__ == "__main__":
    main()

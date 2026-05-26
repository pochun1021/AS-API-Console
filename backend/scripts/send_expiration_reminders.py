from __future__ import annotations

import argparse
import logging
from asyncio import run as run_async
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from sqlalchemy import select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_TZ = ZoneInfo("Asia/Taipei")
LOG_DIR = PROJECT_ROOT / "log" / "send_expiration_reminders"
LOGGER_NAME = "send_expiration_reminders"
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings
from app.services.mail_service import MailService
from db import models  # noqa: F401
from db.models.api_keys import ApiKey
from db.models.applications import ApiKeyApplication
from db.session import SessionLocal


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
    parser = argparse.ArgumentParser(description="Send API key expiration reminders for keys expiring in 30 days.")
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


def _target_window(now: datetime) -> tuple[datetime, datetime]:
    target_day = (now + timedelta(days=30)).date()
    start = datetime(target_day.year, target_day.month, target_day.day, tzinfo=UTC)
    end = start + timedelta(days=1)
    return start, end


def run_once(*, batch_size: int, dry_run: bool, logger: logging.Logger) -> tuple[int, int]:
    now = datetime.now(UTC)
    window_start, window_end = _target_window(now)
    stmt = (
        select(ApiKey, ApiKeyApplication)
        .join(ApiKeyApplication, ApiKey.application_id == ApiKeyApplication.id)
        .where(ApiKey.status == "active")
        .where(ApiKey.expiration_notice_sent_at.is_(None))
        .where(ApiKeyApplication.expires_at >= window_start)
        .where(ApiKeyApplication.expires_at < window_end)
        .order_by(ApiKeyApplication.expires_at.asc(), ApiKey.id.asc())
        .limit(batch_size)
    )

    with SessionLocal() as session:
        rows = session.execute(stmt).all()
        if dry_run:
            return len(rows), 0

        mail_service = MailService()
        settings = get_settings()
        processed = 0
        success = 0
        for row in rows:
            processed += 1
            key = row.ApiKey
            app = row.ApiKeyApplication
            try:
                run_async(
                    mail_service.send_key_expiration_notice(
                        to_email=app.email,
                        owner_name=app.name,
                        expires_at=app.expires_at,
                        app_domain=settings.app_domain,
                    )
                )
                key.expiration_notice_sent_at = datetime.now(UTC)
                session.add(key)
                session.commit()
                success += 1
            except Exception:  # noqa: BLE001
                session.rollback()
                logger.exception(
                    "event=expiration_reminder_send_failed key_id=%s application_id=%s expires_at=%s email=%s",
                    key.id,
                    app.id,
                    app.expires_at.isoformat(),
                    app.email,
                )
        return processed, success


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

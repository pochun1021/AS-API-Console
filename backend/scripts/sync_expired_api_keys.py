from __future__ import annotations

import argparse
import logging
from datetime import UTC, datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from sqlalchemy import select, update

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_TZ = ZoneInfo("Asia/Taipei")
LOG_DIR = PROJECT_ROOT / "log" / "sync_expired_api_keys"
LOGGER_NAME = "sync_expired_api_keys"
sys.path.insert(0, str(BACKEND_ROOT))

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
    parser = argparse.ArgumentParser(
        description="Sync expired API keys from effective status into DB status fields."
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Maximum rows to update per batch (default: 1000).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show number of rows that would be updated without committing changes.",
    )
    return parser.parse_args()


def _collect_target_key_ids(*, batch_size: int) -> list[str]:
    now = datetime.now(UTC)
    stmt = (
        select(ApiKey.id)
        .join(ApiKeyApplication, ApiKey.application_id == ApiKeyApplication.id)
        .where(ApiKey.status == "active")
        .where(ApiKeyApplication.expires_at < now)
        .limit(batch_size)
    )

    with SessionLocal() as session:
        return [row[0] for row in session.execute(stmt).all()]


def run_once(*, batch_size: int, dry_run: bool) -> int:
    key_ids = _collect_target_key_ids(batch_size=batch_size)
    if not key_ids:
        return 0

    if dry_run:
        return len(key_ids)

    now = datetime.now(UTC)
    with SessionLocal() as session:
        session.execute(update(ApiKey).where(ApiKey.id.in_(key_ids)).values(status="expired"))
        session.execute(
            update(ApiKeyApplication)
            .where(ApiKeyApplication.id.in_(select(ApiKey.application_id).where(ApiKey.id.in_(key_ids))))
            .values(status="expired", updated_at=now)
        )
        session.commit()
    return len(key_ids)


def main() -> None:
    args = parse_args()
    logger = _build_logger()
    mode = "dry-run" if args.dry_run else "sync"
    try:
        updated = run_once(batch_size=args.batch_size, dry_run=args.dry_run)
    except Exception:
        logger.exception(
            "event=expired_key_sync mode=%s batch_size=%s dry_run=%s status=failed",
            mode,
            args.batch_size,
            args.dry_run,
        )
        raise SystemExit(1)

    message = f"expired-key-{mode} updated_count={updated} batch_size={args.batch_size}"
    print(message)
    logger.info(
        "event=expired_key_sync mode=%s updated_count=%s batch_size=%s dry_run=%s status=success",
        mode,
        updated,
        args.batch_size,
        args.dry_run,
    )


if __name__ == "__main__":
    main()

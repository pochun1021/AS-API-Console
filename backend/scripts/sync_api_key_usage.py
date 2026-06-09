from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
import sys
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import Select, func, literal, select, update

BACKEND_ROOT = Path(__file__).resolve().parents[1]
LOG_TZ = ZoneInfo("Asia/Taipei")
LOG_ROOT = Path(os.getenv("SCHEDULER_LOG_ROOT", "/home/app/log"))
LOG_DIR = LOG_ROOT / "sync_api_key_usage"
LOGGER_NAME = "sync_api_key_usage"
sys.path.insert(0, str(BACKEND_ROOT))

from db import models  # noqa: F401
from db.models.api_key_usage_snapshots import ApiKeyUsageSnapshot
from db.models.api_keys import ApiKey
from db.models.applications import ApiKeyApplication
from db.session import SessionLocal
from app.services.provider_client import ProviderBadRequestError, ProviderClient, ProviderUnavailableError


@dataclass(slots=True)
class UsageSyncCandidate:
    key_id: str
    key_alias: str


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


def _now_utc() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _round_money(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.0001")))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync API key usage snapshots from provider spend logs.")
    parser.add_argument("--batch-size", type=int, default=100, help="Maximum active keys to sync per run (default: 100).")
    parser.add_argument("--dry-run", action="store_true", help="Compute candidate count without writing snapshots.")
    return parser.parse_args()


def _collect_candidates(*, batch_size: int) -> list[UsageSyncCandidate]:
    effective_key_alias = func.coalesce(ApiKey.key_alias, literal("for_") + ApiKeyApplication.account).label("effective_key_alias")
    stmt: Select = (
        select(ApiKey.id, effective_key_alias)
        .join(ApiKeyApplication, ApiKey.application_id == ApiKeyApplication.id)
        .where(ApiKey.status == "active")
        .order_by(ApiKey.created_at.asc(), ApiKey.id.asc())
        .limit(batch_size)
    )
    with SessionLocal() as session:
        rows = session.execute(stmt).all()
    return [UsageSyncCandidate(key_id=row.id, key_alias=row.effective_key_alias) for row in rows]


def _coerce_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _fetch_spend_snapshot(provider_client: ProviderClient, *, key_alias: str) -> tuple[float, datetime | None]:
    page = 1
    total_pages = 1
    total_spend = Decimal("0")
    budget_reset_at: datetime | None = None

    while page <= total_pages:
        payload = provider_client.list_spend_logs(
            {
                "key_alias": key_alias,
                "status_filter": "success",
                "page": page,
                "page_size": 100,
                "sort_by": "startTime",
                "sort_order": "desc",
            }
        )
        if not isinstance(payload, dict):
            raise ProviderUnavailableError("provider unavailable")
        records = payload.get("data")
        if not isinstance(records, list):
            raise ProviderUnavailableError("provider unavailable")
        total_pages = int(payload.get("total_pages") or 1)
        if budget_reset_at is None:
            budget_reset_at = _coerce_datetime(payload.get("budget_reset_at"))
        for record in records:
            if not isinstance(record, dict):
                continue
            if str(record.get("status") or "").strip().lower() != "success":
                continue
            try:
                total_spend += Decimal(str(record.get("spend") or 0))
            except Exception:  # noqa: BLE001
                continue
        page += 1

    return _round_money(float(total_spend)), budget_reset_at


def run_once(*, batch_size: int, dry_run: bool, logger: logging.Logger | None = None) -> int:
    candidates = _collect_candidates(batch_size=batch_size)
    if dry_run or not candidates:
        return len(candidates)

    provider_client = ProviderClient()
    now = _now_utc()
    updated = 0
    for candidate in candidates:
        try:
            spend, budget_reset_at = _fetch_spend_snapshot(provider_client, key_alias=candidate.key_alias)
        except (ProviderUnavailableError, ProviderBadRequestError) as exc:
            if logger is not None:
                logger.warning(
                    "event=api_key_usage_sync key_id=%s key_alias=%s status=skipped error=%s",
                    candidate.key_id,
                    candidate.key_alias,
                    str(exc),
                )
            continue

        with SessionLocal() as session:
            session.add(
                ApiKeyUsageSnapshot(
                    id=str(uuid4()),
                    api_key_id=candidate.key_id,
                    spend=spend,
                    budget_reset_at=budget_reset_at,
                    synced_at=now,
                    created_at=now,
                )
            )
            session.execute(
                update(ApiKey)
                .where(ApiKey.id == candidate.key_id)
                .values(
                    usage_spend=spend,
                    usage_budget_reset_at=budget_reset_at,
                    usage_synced_at=now,
                )
            )
            session.commit()
        updated += 1
    return updated


def main() -> None:
    args = parse_args()
    logger = _build_logger()
    mode = "dry-run" if args.dry_run else "sync"
    try:
        updated = run_once(batch_size=args.batch_size, dry_run=args.dry_run, logger=logger)
    except Exception:
        logger.exception(
            "event=api_key_usage_sync mode=%s batch_size=%s dry_run=%s status=failed",
            mode,
            args.batch_size,
            args.dry_run,
        )
        raise SystemExit(1)

    print(f"api-key-usage-{mode} updated_count={updated} batch_size={args.batch_size}")
    logger.info(
        "event=api_key_usage_sync mode=%s updated_count=%s batch_size=%s dry_run=%s status=success",
        mode,
        updated,
        args.batch_size,
        args.dry_run,
    )


if __name__ == "__main__":
    main()

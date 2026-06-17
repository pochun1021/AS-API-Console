from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
import sys
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import Select, func, inspect, literal, select, update

BACKEND_ROOT = Path(__file__).resolve().parents[1]
LOG_TZ = ZoneInfo("Asia/Taipei")
LOG_ROOT = Path(os.getenv("SCHEDULER_LOG_ROOT", "/home/app/log"))
LOG_DIR = LOG_ROOT / "sync_api_key_usage"
LOGGER_NAME = "sync_api_key_usage"
TAIPEI_TZ = ZoneInfo("Asia/Taipei")
ROLLING_DAYS = 30
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


@dataclass(slots=True)
class DailyUsageBucket:
    bucket_date: date
    bucket_start_utc: datetime
    bucket_end_utc: datetime
    spend: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class UsageSnapshotSchemaError(RuntimeError):
    """Raised when usage snapshot schema is older than the script expects."""


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


def _coerce_int(value: object) -> int:
    try:
        normalized = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return normalized if normalized >= 0 else 0


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


def _ensure_usage_snapshot_schema(session) -> None:
    required_columns = {"bucket_granularity", "bucket_start_utc", "bucket_end_utc"}
    inspector = inspect(session.bind)
    existing_columns = {column["name"] for column in inspector.get_columns("api_key_usage_snapshots")}
    missing_columns = sorted(required_columns - existing_columns)
    if not missing_columns:
        return
    missing = ", ".join(missing_columns)
    raise UsageSnapshotSchemaError(
        "api_key_usage_snapshots schema is missing required columns: "
        f"{missing}. Run 'cd backend && uv run alembic upgrade head' before sync_api_key_usage."
    )


def _coerce_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _format_provider_datetime(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _build_rolling_window(now: datetime) -> tuple[datetime, datetime]:
    local_today = now.astimezone(TAIPEI_TZ).date()
    local_start = datetime.combine(local_today - timedelta(days=ROLLING_DAYS - 1), time.min, tzinfo=TAIPEI_TZ)
    local_end_exclusive = datetime.combine(local_today + timedelta(days=1), time.min, tzinfo=TAIPEI_TZ)
    return local_start.astimezone(UTC), local_end_exclusive.astimezone(UTC)


def _bucket_bounds_for_local_day(bucket_date: date) -> tuple[datetime, datetime]:
    local_start = datetime.combine(bucket_date, time.min, tzinfo=TAIPEI_TZ)
    local_end = local_start + timedelta(days=1)
    return local_start.astimezone(UTC), local_end.astimezone(UTC)


def _build_daily_buckets(payload: object) -> tuple[list[DailyUsageBucket], datetime | None]:
    if not isinstance(payload, dict):
        raise ProviderUnavailableError("provider unavailable")
    records = payload.get("data")
    if not isinstance(records, list):
        raise ProviderUnavailableError("provider unavailable")

    grouped: dict[date, dict[str, Decimal | int]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        if str(record.get("status") or "").strip().lower() != "success":
            continue
        start_time = _coerce_datetime(record.get("startTime"))
        if start_time is None:
            continue
        bucket_date = start_time.astimezone(TAIPEI_TZ).date()
        bucket = grouped.setdefault(
            bucket_date,
            {
                "spend": Decimal("0"),
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        )
        try:
            bucket["spend"] += Decimal(str(record.get("spend") or 0))
        except Exception:  # noqa: BLE001
            continue
        bucket["prompt_tokens"] += _coerce_int(record.get("prompt_tokens"))
        bucket["completion_tokens"] += _coerce_int(record.get("completion_tokens"))
        bucket["total_tokens"] += _coerce_int(record.get("total_tokens"))

    budget_reset_at = _coerce_datetime(payload.get("budget_reset_at"))
    items: list[DailyUsageBucket] = []
    for bucket_date in sorted(grouped.keys()):
        bucket_start_utc, bucket_end_utc = _bucket_bounds_for_local_day(bucket_date)
        aggregate = grouped[bucket_date]
        items.append(
            DailyUsageBucket(
                bucket_date=bucket_date,
                bucket_start_utc=bucket_start_utc,
                bucket_end_utc=bucket_end_utc,
                spend=_round_money(float(aggregate["spend"])),
                prompt_tokens=int(aggregate["prompt_tokens"]),
                completion_tokens=int(aggregate["completion_tokens"]),
                total_tokens=int(aggregate["total_tokens"]),
            )
        )
    return items, budget_reset_at


def _fetch_spend_buckets(
    provider_client: ProviderClient,
    *,
    key_alias: str,
    now: datetime,
) -> tuple[list[DailyUsageBucket], datetime | None]:
    page = 1
    total_pages = 1
    budget_reset_at: datetime | None = None
    start_at, end_at_exclusive = _build_rolling_window(now)
    start_date = _format_provider_datetime(start_at)
    end_date = _format_provider_datetime(end_at_exclusive - timedelta(seconds=1))
    grouped: dict[date, DailyUsageBucket] = {}

    while page <= total_pages:
        payload = provider_client.list_spend_logs(
            {
                "start_date": start_date,
                "end_date": end_date,
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
        total_pages = int(payload.get("total_pages") or 1)
        items, page_budget_reset_at = _build_daily_buckets(payload)
        if budget_reset_at is None:
            budget_reset_at = page_budget_reset_at
        for item in items:
            existing = grouped.get(item.bucket_date)
            if existing is None:
                grouped[item.bucket_date] = item
                continue
            grouped[item.bucket_date] = DailyUsageBucket(
                bucket_date=item.bucket_date,
                bucket_start_utc=item.bucket_start_utc,
                bucket_end_utc=item.bucket_end_utc,
                spend=_round_money(existing.spend + item.spend),
                prompt_tokens=existing.prompt_tokens + item.prompt_tokens,
                completion_tokens=existing.completion_tokens + item.completion_tokens,
                total_tokens=existing.total_tokens + item.total_tokens,
            )
        page += 1

    return [grouped[key] for key in sorted(grouped.keys())], budget_reset_at


def _upsert_daily_bucket(
    *,
    session,
    key_id: str,
    item: DailyUsageBucket,
    budget_reset_at: datetime | None,
    synced_at: datetime,
) -> None:
    existing = session.scalar(
        select(ApiKeyUsageSnapshot).where(
            ApiKeyUsageSnapshot.api_key_id == key_id,
            ApiKeyUsageSnapshot.bucket_granularity == "day",
            ApiKeyUsageSnapshot.bucket_start_utc == item.bucket_start_utc,
        )
    )
    if existing is None:
        existing = ApiKeyUsageSnapshot(
            id=str(uuid4()),
            api_key_id=key_id,
            bucket_granularity="day",
            bucket_start_utc=item.bucket_start_utc,
            bucket_end_utc=item.bucket_end_utc,
            created_at=synced_at,
        )
    existing.spend = item.spend
    existing.prompt_tokens = item.prompt_tokens
    existing.completion_tokens = item.completion_tokens
    existing.total_tokens = item.total_tokens
    existing.budget_reset_at = budget_reset_at
    existing.synced_at = synced_at
    session.add(existing)


def run_once(*, batch_size: int, dry_run: bool, logger: logging.Logger | None = None) -> int:
    candidates = _collect_candidates(batch_size=batch_size)
    if dry_run or not candidates:
        return len(candidates)

    with SessionLocal() as session:
        _ensure_usage_snapshot_schema(session)

    provider_client = ProviderClient()
    now = _now_utc()
    updated = 0
    for candidate in candidates:
        try:
            daily_buckets, budget_reset_at = _fetch_spend_buckets(
                provider_client,
                key_alias=candidate.key_alias,
                now=now,
            )
        except (ProviderUnavailableError, ProviderBadRequestError) as exc:
            if logger is not None:
                logger.warning(
                    "event=api_key_usage_sync key_id=%s key_alias=%s status=skipped error=%s",
                    candidate.key_id,
                    candidate.key_alias,
                    str(exc),
                )
            continue

        latest_bucket = daily_buckets[-1] if daily_buckets else None
        with SessionLocal() as session:
            for bucket in daily_buckets:
                _upsert_daily_bucket(
                    session=session,
                    key_id=candidate.key_id,
                    item=bucket,
                    budget_reset_at=budget_reset_at,
                    synced_at=now,
                )
            session.execute(
                update(ApiKey)
                .where(ApiKey.id == candidate.key_id)
                .values(
                    usage_spend=latest_bucket.spend if latest_bucket is not None else None,
                    usage_budget_reset_at=budget_reset_at if latest_bucket is not None else None,
                    usage_synced_at=now if latest_bucket is not None else None,
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

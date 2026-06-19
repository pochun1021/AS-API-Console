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

from sqlalchemy import Select, and_, exists, func, inspect, literal, or_, select, update

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
from db.models.limit_strategy_config import LimitStrategyConfig
from db.session import SessionLocal
from app.services.provider_client import ProviderBadRequestError, ProviderClient, ProviderUnavailableError

LIMIT_STRATEGY_CONFIG_ID = "global-limit-strategy-config"

@dataclass(slots=True)
class UsageSyncCandidate:
    key_id: str
    key_hash: str
    key_alias: str


@dataclass(slots=True)
class SyncRunStats:
    candidate_key_count: int = 0
    processed_key_count: int = 0
    history_written_count: int = 0
    cache_written_count: int = 0
    cache_skipped_count: int = 0


@dataclass(slots=True)
class DailyUsageBucket:
    bucket_date: date
    bucket_start_utc: datetime
    bucket_end_utc: datetime
    spend: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(slots=True)
class ProviderUsageRecord:
    start_time: datetime
    spend: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(slots=True)
class ProviderSpendKeySummary:
    spend: float | None
    budget_duration: str | None
    budget_reset_at: datetime | None
    synced_at: datetime | None
    token: str | None
    key_alias: str | None


@dataclass(slots=True)
class UsageAggregate:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class UsageSnapshotSchemaError(RuntimeError):
    """Raised when usage snapshot schema is older than the script expects."""


class ProviderPaginationMetadataError(RuntimeError):
    """Raised when provider paging metadata is inconsistent or untrustworthy."""


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


def _budget_duration_days(duration: str | None) -> int | None:
    normalized = str(duration or "").strip().lower()
    if normalized == "daily":
        return 1
    if normalized == "weekly":
        return 7
    if normalized == "monthly":
        return 30
    return None


def _get_current_budget_duration() -> str:
    with SessionLocal() as session:
        config = session.get(LimitStrategyConfig, LIMIT_STRATEGY_CONFIG_ID)
    if config is None:
        return "monthly"
    normalized = str(config.budget_duration or "").strip().lower()
    return normalized or "monthly"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync API key usage snapshots from provider spend logs.")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Chunk size for each active-key batch and provider page size expectation (default: 100).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Compute candidate count without writing snapshots.")
    parser.add_argument(
        "--repair-missing-cache",
        action="store_true",
        help="Only process active keys whose current-cycle usage cache is missing or incomplete.",
    )
    return parser.parse_args()


def _collect_candidates(*, batch_size: int, offset: int = 0, repair_missing_cache: bool = False) -> list[UsageSyncCandidate]:
    effective_key_alias = func.coalesce(ApiKey.key_alias, literal("for_") + ApiKeyApplication.account).label("effective_key_alias")
    stmt: Select = (
        select(ApiKey.id, ApiKey.key_hash, effective_key_alias)
        .join(ApiKeyApplication, ApiKey.application_id == ApiKeyApplication.id)
        .where(ApiKey.status == "active")
        .order_by(ApiKey.created_at.asc(), ApiKey.id.asc())
        .offset(offset)
        .limit(batch_size)
    )
    if repair_missing_cache:
        has_usage_history = exists(
            select(ApiKeyUsageSnapshot.id).where(
                ApiKeyUsageSnapshot.api_key_id == ApiKey.id,
                ApiKeyUsageSnapshot.bucket_granularity == "day",
            )
        )
        stmt = stmt.where(
            and_(
                has_usage_history,
                or_(
                    ApiKey.usage_synced_at.is_(None),
                    ApiKey.usage_budget_reset_at.is_(None),
                    and_(
                        ApiKey.usage_spend.is_(None),
                        ApiKey.usage_prompt_tokens.is_(None),
                        ApiKey.usage_completion_tokens.is_(None),
                        ApiKey.usage_total_tokens.is_(None),
                    ),
                ),
            )
        )
    with SessionLocal() as session:
        rows = session.execute(stmt).all()
    return [
        UsageSyncCandidate(
            key_id=row.id,
            key_hash=row.key_hash,
            key_alias=row.effective_key_alias,
        )
        for row in rows
    ]


def _count_candidates(*, repair_missing_cache: bool = False) -> int:
    stmt = select(func.count(ApiKey.id)).join(ApiKeyApplication, ApiKey.application_id == ApiKeyApplication.id).where(ApiKey.status == "active")
    if repair_missing_cache:
        has_usage_history = exists(
            select(ApiKeyUsageSnapshot.id).where(
                ApiKeyUsageSnapshot.api_key_id == ApiKey.id,
                ApiKeyUsageSnapshot.bucket_granularity == "day",
            )
        )
        stmt = stmt.where(
            and_(
                has_usage_history,
                or_(
                    ApiKey.usage_synced_at.is_(None),
                    ApiKey.usage_budget_reset_at.is_(None),
                    and_(
                        ApiKey.usage_spend.is_(None),
                        ApiKey.usage_prompt_tokens.is_(None),
                        ApiKey.usage_completion_tokens.is_(None),
                        ApiKey.usage_total_tokens.is_(None),
                    ),
                ),
            )
        )
    with SessionLocal() as session:
        return int(session.scalar(stmt) or 0)


def _collect_all_candidates(*, batch_size: int, repair_missing_cache: bool = False) -> list[UsageSyncCandidate]:
    candidates: list[UsageSyncCandidate] = []
    offset = 0
    while True:
        batch = _collect_candidates(
            batch_size=batch_size,
            offset=offset,
            repair_missing_cache=repair_missing_cache,
        )
        if not batch:
            break
        candidates.extend(batch)
        offset += len(batch)
    return candidates


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


def _extract_spend_key_summaries(payload: object) -> dict[tuple[str, str], ProviderSpendKeySummary]:
    if isinstance(payload, dict):
        records = payload.get("data")
        if not isinstance(records, list):
            raise ProviderUnavailableError("provider unavailable")
    elif isinstance(payload, list):
        records = payload
    else:
        raise ProviderUnavailableError("provider unavailable")

    summaries: dict[tuple[str, str], ProviderSpendKeySummary] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        token = str(record.get("token") or "").strip() or None
        key_alias = str(record.get("key_alias") or "").strip() or None
        spend_value: float | None = None
        if record.get("spend") is not None:
            try:
                spend_value = _round_money(float(Decimal(str(record.get("spend")))))
            except Exception:  # noqa: BLE001
                spend_value = None
        summary = ProviderSpendKeySummary(
            spend=spend_value,
            budget_duration=str(record.get("budget_duration") or "").strip().lower() or None,
            budget_reset_at=_coerce_datetime(record.get("budget_reset_at")),
            synced_at=_coerce_datetime(record.get("updated_at")),
            token=token,
            key_alias=key_alias,
        )
        if token is not None:
            summaries[("token", token)] = summary
        if key_alias is not None:
            summaries[("alias", key_alias)] = summary
    return summaries


def _extract_success_records(payload: object) -> list[ProviderUsageRecord]:
    if not isinstance(payload, dict):
        raise ProviderUnavailableError("provider unavailable")
    records = payload.get("data")
    if not isinstance(records, list):
        raise ProviderUnavailableError("provider unavailable")

    items: list[ProviderUsageRecord] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        if str(record.get("status") or "").strip().lower() != "success":
            continue
        start_time = _coerce_datetime(record.get("startTime"))
        if start_time is None:
            continue
        try:
            spend = _round_money(float(Decimal(str(record.get("spend") or 0))))
        except Exception:  # noqa: BLE001
            continue
        items.append(
            ProviderUsageRecord(
                start_time=start_time,
                spend=spend,
                prompt_tokens=_coerce_int(record.get("prompt_tokens")),
                completion_tokens=_coerce_int(record.get("completion_tokens")),
                total_tokens=_coerce_int(record.get("total_tokens")),
            )
        )

    return items


def _build_daily_buckets(records: list[ProviderUsageRecord]) -> list[DailyUsageBucket]:
    grouped: dict[date, dict[str, Decimal | int]] = {}
    for record in records:
        bucket_date = record.start_time.astimezone(TAIPEI_TZ).date()
        bucket = grouped.setdefault(
            bucket_date,
            {
                "spend": Decimal("0"),
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        )
        bucket["spend"] += Decimal(str(record.spend))
        bucket["prompt_tokens"] += record.prompt_tokens
        bucket["completion_tokens"] += record.completion_tokens
        bucket["total_tokens"] += record.total_tokens

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
    return items


def _build_current_cycle_aggregate(
    records: list[ProviderUsageRecord],
    *,
    budget_reset_at: datetime | None,
    budget_duration: str | None,
) -> UsageAggregate | None:
    duration_days = _budget_duration_days(budget_duration)
    if budget_reset_at is None or duration_days is None:
        return None

    cycle_start = budget_reset_at.astimezone(UTC) - timedelta(days=duration_days)
    cycle_end = budget_reset_at.astimezone(UTC)
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0

    for record in records:
        record_time = record.start_time.astimezone(UTC)
        if record_time < cycle_start or record_time >= cycle_end:
            continue
        prompt_tokens += record.prompt_tokens
        completion_tokens += record.completion_tokens
        total_tokens += record.total_tokens

    return UsageAggregate(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )


def _coerce_non_negative_int(value: object, field_name: str) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise ProviderPaginationMetadataError(f"invalid {field_name}") from exc
    if normalized < 0:
        raise ProviderPaginationMetadataError(f"invalid {field_name}")
    return normalized


def _validate_paging_metadata(
    *,
    payload: dict,
    expected_page: int,
    expected_page_size: int,
    is_last_page: bool | None = None,
) -> tuple[list[object], int, int, int, int]:
    records = payload.get("data")
    if not isinstance(records, list):
        raise ProviderPaginationMetadataError("invalid data")

    total = _coerce_non_negative_int(payload.get("total"), "total")
    page = _coerce_non_negative_int(payload.get("page"), "page")
    page_size = _coerce_non_negative_int(payload.get("page_size"), "page_size")
    total_pages = _coerce_non_negative_int(payload.get("total_pages"), "total_pages")

    if page < 1:
        raise ProviderPaginationMetadataError("invalid page")
    if page_size < 1:
        raise ProviderPaginationMetadataError("invalid page_size")
    if page != expected_page:
        raise ProviderPaginationMetadataError("unexpected page")
    if page_size != expected_page_size:
        raise ProviderPaginationMetadataError("unexpected page_size")
    if total_pages == 0:
        if total != 0 or records:
            raise ProviderPaginationMetadataError("inconsistent empty pagination")
        return records, total, page, page_size, total_pages
    if page > total_pages:
        raise ProviderPaginationMetadataError("page exceeds total_pages")
    if len(records) > page_size:
        raise ProviderPaginationMetadataError("page contains more records than page_size")
    if is_last_page is False and not records:
        raise ProviderPaginationMetadataError("non-final page cannot be empty")
    return records, total, page, page_size, total_pages


def _fetch_spend_buckets(
    provider_client: ProviderClient,
    *,
    api_key: str,
    now: datetime,
) -> list[ProviderUsageRecord]:
    page = 1
    total_pages = 1
    expected_page_size = 100
    start_at, end_at_exclusive = _build_rolling_window(now)
    start_date = _format_provider_datetime(start_at)
    end_date = _format_provider_datetime(end_at_exclusive - timedelta(seconds=1))
    items: list[ProviderUsageRecord] = []
    total_records_expected: int | None = None

    while page <= total_pages:
        payload = provider_client.list_spend_logs(
            {
                "start_date": start_date,
                "end_date": end_date,
                "api_key": api_key,
                "status_filter": "success",
                "page": page,
                "page_size": expected_page_size,
                "sort_by": "startTime",
                "sort_order": "desc",
            }
        )
        if not isinstance(payload, dict):
            raise ProviderUnavailableError("provider unavailable")
        _, total, response_page, response_page_size, response_total_pages = _validate_paging_metadata(
            payload=payload,
            expected_page=page,
            expected_page_size=expected_page_size,
            is_last_page=None if total_pages == 1 else page == total_pages,
        )
        if total_records_expected is None:
            total_records_expected = total
        elif total != total_records_expected:
            raise ProviderPaginationMetadataError("inconsistent total across pages")
        total_pages = response_total_pages
        _validate_paging_metadata(
            payload=payload,
            expected_page=response_page,
            expected_page_size=response_page_size,
            is_last_page=response_page == response_total_pages if response_total_pages > 0 else True,
        )
        page_items = _extract_success_records(payload)
        items.extend(page_items)
        page += 1

    if total_records_expected is not None:
        if total_records_expected == 0 and items:
            raise ProviderPaginationMetadataError("expected zero records but received data")
        if len(items) > total_records_expected:
            raise ProviderPaginationMetadataError("received more records than total")

    return items


def _fetch_spend_key_summaries(provider_client: ProviderClient) -> dict[tuple[str, str], ProviderSpendKeySummary]:
    payload = provider_client.list_spend_keys()
    return _extract_spend_key_summaries(payload)


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


def _log_cache_skipped(
    *,
    logger: logging.Logger | None,
    candidate: UsageSyncCandidate,
    reason: str,
) -> None:
    if logger is None:
        return
    logger.warning(
        "event=api_key_usage_sync key_id=%s key_alias=%s status=cache_skipped reason=%s",
        candidate.key_id,
        candidate.key_alias,
        reason,
    )


def run_once(*, batch_size: int, dry_run: bool, repair_missing_cache: bool = False, logger: logging.Logger | None = None) -> int:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")

    candidates = _collect_all_candidates(batch_size=batch_size, repair_missing_cache=repair_missing_cache)
    if dry_run or not candidates:
        return len(candidates)

    with SessionLocal() as session:
        _ensure_usage_snapshot_schema(session)

    provider_client = ProviderClient()
    try:
        spend_key_summaries = _fetch_spend_key_summaries(provider_client)
    except (ProviderUnavailableError, ProviderBadRequestError) as exc:
        spend_key_summaries = {}
        if logger is not None:
            logger.warning("event=api_key_usage_sync stage=summary_sync status=failed error=%s", str(exc))
    now = _now_utc()
    current_budget_duration = _get_current_budget_duration()
    stats = SyncRunStats(candidate_key_count=len(candidates))
    for candidate in candidates:
        try:
            records = _fetch_spend_buckets(
                provider_client,
                api_key=candidate.key_hash,
                now=now,
            )
        except (ProviderUnavailableError, ProviderBadRequestError, ProviderPaginationMetadataError) as exc:
            if logger is not None:
                logger.warning(
                    "event=api_key_usage_sync key_id=%s key_alias=%s status=skipped error=%s",
                    candidate.key_id,
                    candidate.key_alias,
                    str(exc),
                )
            continue

        summary = spend_key_summaries.get(("token", candidate.key_hash)) or spend_key_summaries.get(("alias", candidate.key_alias))

        daily_buckets = _build_daily_buckets(records)
        current_cycle = _build_current_cycle_aggregate(
            records,
            budget_reset_at=summary.budget_reset_at if summary is not None else None,
            budget_duration=current_budget_duration,
        )
        with SessionLocal() as session:
            for bucket in daily_buckets:
                _upsert_daily_bucket(
                    session=session,
                    key_id=candidate.key_id,
                    item=bucket,
                    budget_reset_at=summary.budget_reset_at if summary is not None else None,
                    synced_at=now,
                )
            cache_values: dict[str, object] | None = None
            if summary is not None:
                cache_values = {
                    "usage_spend": summary.spend,
                    "usage_prompt_tokens": current_cycle.prompt_tokens if current_cycle is not None else None,
                    "usage_completion_tokens": current_cycle.completion_tokens if current_cycle is not None else None,
                    "usage_total_tokens": current_cycle.total_tokens if current_cycle is not None else None,
                    "usage_budget_reset_at": summary.budget_reset_at,
                    "usage_synced_at": summary.synced_at or now,
                }
            if cache_values is not None:
                session.execute(
                    update(ApiKey)
                    .where(ApiKey.id == candidate.key_id)
                    .values(**cache_values)
                )
            session.commit()

        stats.processed_key_count += 1
        stats.history_written_count += len(daily_buckets)
        if summary is not None:
            stats.cache_written_count += 1
        else:
            stats.cache_skipped_count += 1
            _log_cache_skipped(logger=logger, candidate=candidate, reason="missing_spend_key_summary")
        if summary is not None and current_cycle is None:
            stats.cache_skipped_count += 1
            _log_cache_skipped(logger=logger, candidate=candidate, reason="missing_current_cycle_window")

    if logger is not None:
        logger.info(
            "event=api_key_usage_sync mode=%s candidate_key_count=%s processed_key_count=%s history_written_count=%s cache_written_count=%s cache_skipped_count=%s status=success",
            "repair-missing-cache" if repair_missing_cache else "sync",
            stats.candidate_key_count,
            stats.processed_key_count,
            stats.history_written_count,
            stats.cache_written_count,
            stats.cache_skipped_count,
        )
    return stats.processed_key_count


def main() -> None:
    args = parse_args()
    logger = _build_logger()
    mode = "dry-run" if args.dry_run else ("repair-missing-cache" if args.repair_missing_cache else "sync")
    try:
        updated = run_once(
            batch_size=args.batch_size,
            dry_run=args.dry_run,
            repair_missing_cache=args.repair_missing_cache,
            logger=logger,
        )
    except Exception:
        logger.exception(
            "event=api_key_usage_sync mode=%s batch_size=%s dry_run=%s repair_missing_cache=%s status=failed",
            mode,
            args.batch_size,
            args.dry_run,
            args.repair_missing_cache,
        )
        raise SystemExit(1)

    print(f"api-key-usage-{mode} updated_count={updated} batch_size={args.batch_size}")
    logger.info(
        "event=api_key_usage_sync mode=%s updated_count=%s batch_size=%s dry_run=%s repair_missing_cache=%s status=success",
        mode,
        updated,
        args.batch_size,
        args.dry_run,
        args.repair_missing_cache,
    )


if __name__ == "__main__":
    main()

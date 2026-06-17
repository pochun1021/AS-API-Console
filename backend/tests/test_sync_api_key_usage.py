from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from tests.conftest import api_path as _api


def _fetch_usage_snapshot_rows(key_id: str) -> list[dict]:
    settings = get_settings()
    db_url = settings.test_database_url or settings.database_url
    engine = create_engine(db_url, future=True)
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT api_key_id, bucket_granularity, bucket_start_utc, bucket_end_utc,
                       spend, prompt_tokens, completion_tokens, total_tokens, budget_reset_at, synced_at
                FROM api_key_usage_snapshots
                WHERE api_key_id = :key_id
                ORDER BY bucket_start_utc ASC, synced_at DESC
                """
            ),
            {"key_id": key_id},
        ).mappings().all()
    return [dict(row) for row in rows]


def test_usage_sync_script_records_daily_bucket_history_and_cache(client, admin_headers, user_headers, monkeypatch):
    from scripts import sync_api_key_usage

    settings = get_settings()
    db_url = settings.test_database_url or settings.database_url
    usage_engine = create_engine(db_url, future=True)
    monkeypatch.setattr(
        "scripts.sync_api_key_usage.SessionLocal",
        sessionmaker(bind=usage_engine, autoflush=False, autocommit=False, class_=Session),
    )

    whitelist_resp = client.post(
        _api("/whitelists"),
        headers=admin_headers,
        json={
            "sysid": int(user_headers["x-sysid"]),
            "account": user_headers["x-account"],
            "name": user_headers["x-name"],
            "email": user_headers["x-email"],
            "note": "seed",
        },
    )
    assert whitelist_resp.status_code == 201

    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "sync usage"},
    )
    assert create_resp.status_code == 201
    item = client.get(_api("/api-keys"), headers=user_headers).json()["items"][0]
    key_id = item["id"]
    key_alias = item["key_alias"]

    log_time = datetime.now(UTC).replace(microsecond=0)
    prior_day_log_time = datetime(2026, 6, 7, 15, 30, 0, tzinfo=UTC)
    same_day_log_time = datetime(2026, 6, 8, 2, 0, 0, tzinfo=UTC)
    sync_now = datetime(2026, 6, 8, 12, 34, 56, tzinfo=UTC)
    budget_reset_at = log_time + timedelta(days=7)

    class _FakeProviderClient:
        def list_spend_logs(self, query: dict) -> dict:
            assert query["key_alias"] == key_alias
            assert query["start_date"] == "2026-05-09 16:00:00"
            assert query["end_date"] == "2026-06-08 15:59:59"
            return {
                "data": [
                    {
                        "status": "success",
                        "spend": 0.009805,
                        "prompt_tokens": 123,
                        "completion_tokens": 45,
                        "total_tokens": 168,
                        "startTime": prior_day_log_time.isoformat(),
                        "endTime": prior_day_log_time.isoformat(),
                    },
                    {
                        "status": "success",
                        "spend": 0.5001,
                        "prompt_tokens": 200,
                        "completion_tokens": 20,
                        "total_tokens": 220,
                        "startTime": same_day_log_time.isoformat(),
                        "endTime": same_day_log_time.isoformat(),
                    },
                    {
                        "status": "failure",
                        "spend": 99.0,
                        "prompt_tokens": 999,
                        "completion_tokens": 999,
                        "total_tokens": 1998,
                        "startTime": log_time.isoformat(),
                        "endTime": log_time.isoformat(),
                    },
                ],
                "total": 2,
                "page": 1,
                "page_size": 100,
                "total_pages": 1,
                "budget_reset_at": budget_reset_at.isoformat(),
            }

    monkeypatch.setattr(sync_api_key_usage, "ProviderClient", lambda: _FakeProviderClient())
    monkeypatch.setattr(
        sync_api_key_usage,
        "_now_utc",
        lambda: sync_now,
    )

    updated = sync_api_key_usage.run_once(batch_size=100, dry_run=False)

    assert updated == 1
    rows = _fetch_usage_snapshot_rows(key_id)
    assert len(rows) == 2
    assert rows[0]["bucket_granularity"] == "day"
    assert rows[0]["bucket_start_utc"].replace(tzinfo=UTC) == datetime(2026, 6, 6, 16, 0, 0, tzinfo=UTC)
    assert rows[0]["bucket_end_utc"].replace(tzinfo=UTC) == datetime(2026, 6, 7, 16, 0, 0, tzinfo=UTC)
    assert float(rows[0]["spend"]) == 0.0098
    assert rows[0]["prompt_tokens"] == 123
    assert rows[0]["completion_tokens"] == 45
    assert rows[0]["total_tokens"] == 168
    assert rows[1]["bucket_granularity"] == "day"
    assert rows[1]["bucket_start_utc"].replace(tzinfo=UTC) == datetime(2026, 6, 7, 16, 0, 0, tzinfo=UTC)
    assert rows[1]["bucket_end_utc"].replace(tzinfo=UTC) == datetime(2026, 6, 8, 16, 0, 0, tzinfo=UTC)
    assert float(rows[1]["spend"]) == 0.5001
    assert rows[1]["prompt_tokens"] == 200
    assert rows[1]["completion_tokens"] == 20
    assert rows[1]["total_tokens"] == 220
    assert rows[0]["budget_reset_at"].replace(tzinfo=UTC) == budget_reset_at
    assert rows[0]["synced_at"].replace(tzinfo=UTC) == sync_now

    listed = client.get(_api("/api-keys"), headers=user_headers)
    assert listed.status_code == 200
    assert listed.json()["items"][0]["usage_summary"]["spend"] == 0.5


def test_usage_sync_script_re_run_updates_existing_bucket_without_duplicates(client, admin_headers, user_headers, monkeypatch):
    from scripts import sync_api_key_usage

    settings = get_settings()
    db_url = settings.test_database_url or settings.database_url
    usage_engine = create_engine(db_url, future=True)
    monkeypatch.setattr(
        "scripts.sync_api_key_usage.SessionLocal",
        sessionmaker(bind=usage_engine, autoflush=False, autocommit=False, class_=Session),
    )

    whitelist_resp = client.post(
        _api("/whitelists"),
        headers=admin_headers,
        json={
            "sysid": int(user_headers["x-sysid"]),
            "account": user_headers["x-account"],
            "name": user_headers["x-name"],
            "email": user_headers["x-email"],
            "note": "seed",
        },
    )
    assert whitelist_resp.status_code == 201
    client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "sync usage rerun"},
    )
    item = client.get(_api("/api-keys"), headers=user_headers).json()["items"][0]
    key_id = item["id"]
    key_alias = item["key_alias"]
    sync_now = datetime(2026, 6, 8, 12, 34, 56, tzinfo=UTC)
    bucket_log_time = datetime(2026, 6, 8, 2, 0, 0, tzinfo=UTC)

    class _FakeProviderClient:
        def __init__(self):
            self.calls = 0

        def list_spend_logs(self, query: dict) -> dict:
            self.calls += 1
            assert query["key_alias"] == key_alias
            spend = 0.25 if self.calls == 1 else 0.75
            total_tokens = 100 if self.calls == 1 else 300
            return {
                "data": [
                    {
                        "status": "success",
                        "spend": spend,
                        "prompt_tokens": 80,
                        "completion_tokens": 20,
                        "total_tokens": total_tokens,
                        "startTime": bucket_log_time.isoformat(),
                        "endTime": bucket_log_time.isoformat(),
                    }
                ],
                "total": 1,
                "page": 1,
                "page_size": 100,
                "total_pages": 1,
                "budget_reset_at": (sync_now + timedelta(days=1)).isoformat(),
            }

    fake_client = _FakeProviderClient()
    monkeypatch.setattr(sync_api_key_usage, "ProviderClient", lambda: fake_client)
    monkeypatch.setattr(sync_api_key_usage, "_now_utc", lambda: sync_now)

    assert sync_api_key_usage.run_once(batch_size=100, dry_run=False) == 1
    assert sync_api_key_usage.run_once(batch_size=100, dry_run=False) == 1

    rows = _fetch_usage_snapshot_rows(key_id)
    assert len(rows) == 1
    assert float(rows[0]["spend"]) == 0.75
    assert rows[0]["total_tokens"] == 300


def test_usage_sync_script_fails_fast_when_daily_bucket_columns_are_missing(monkeypatch):
    from scripts import sync_api_key_usage

    class _FakeInspector:
        def get_columns(self, table_name: str) -> list[dict]:
            assert table_name == "api_key_usage_snapshots"
            return [{"name": "id"}, {"name": "api_key_id"}, {"name": "spend"}]

    fake_session = SimpleNamespace(bind=object())
    monkeypatch.setattr(sync_api_key_usage, "inspect", lambda bind: _FakeInspector())

    with pytest.raises(sync_api_key_usage.UsageSnapshotSchemaError) as exc_info:
        sync_api_key_usage._ensure_usage_snapshot_schema(fake_session)

    assert "bucket_granularity" in str(exc_info.value)
    assert "alembic upgrade head" in str(exc_info.value)

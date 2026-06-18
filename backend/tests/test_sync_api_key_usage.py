from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from tests.api_keys_test_utils import _fetch_key_row, _set_limit_strategy_config
from tests.conftest import api_path as _api
from tests.db_runtime import begin_connection, get_test_session_factory


def _fetch_usage_snapshot_rows(key_id: str) -> list[dict]:
    with begin_connection() as conn:
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


def _create_whitelist_for_user(client, admin_headers, user_headers) -> None:
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


def test_usage_sync_script_records_daily_bucket_history_and_cache(client, admin_headers, user_headers, monkeypatch):
    from scripts import sync_api_key_usage

    monkeypatch.setattr("scripts.sync_api_key_usage.SessionLocal", get_test_session_factory())

    _create_whitelist_for_user(client, admin_headers, user_headers)

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
    sync_now = datetime.now(UTC).replace(microsecond=0)
    budget_reset_at = log_time + timedelta(days=7)
    expected_start_at, expected_end_exclusive = sync_api_key_usage._build_rolling_window(sync_now)

    class _FakeProviderClient:
        def list_spend_logs(self, query: dict) -> dict:
            assert query["key_alias"] == key_alias
            assert query["start_date"] == sync_api_key_usage._format_provider_datetime(expected_start_at)
            assert query["end_date"] == sync_api_key_usage._format_provider_datetime(
                expected_end_exclusive - timedelta(seconds=1)
            )
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
    assert listed.json()["items"][0]["usage_summary"]["spend"] == 0.51
    assert listed.json()["items"][0]["usage_summary"]["prompt_tokens"] == 323
    assert listed.json()["items"][0]["usage_summary"]["completion_tokens"] == 65
    assert listed.json()["items"][0]["usage_summary"]["total_tokens"] == 388


def test_usage_sync_script_re_run_updates_existing_bucket_without_duplicates(client, admin_headers, user_headers, monkeypatch):
    from scripts import sync_api_key_usage

    monkeypatch.setattr("scripts.sync_api_key_usage.SessionLocal", get_test_session_factory())

    _create_whitelist_for_user(client, admin_headers, user_headers)
    client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "sync usage rerun"},
    )
    item = client.get(_api("/api-keys"), headers=user_headers).json()["items"][0]
    key_id = item["id"]
    key_alias = item["key_alias"]
    sync_now = datetime.now(UTC).replace(microsecond=0)
    bucket_log_time = sync_now - timedelta(hours=2)

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

    listed = client.get(_api("/api-keys"), headers=user_headers)
    assert listed.status_code == 200
    assert listed.json()["items"][0]["usage_summary"]["total_tokens"] == 300


def test_usage_sync_script_fetches_multiple_provider_pages(client, admin_headers, user_headers, monkeypatch):
    from scripts import sync_api_key_usage

    monkeypatch.setattr("scripts.sync_api_key_usage.SessionLocal", get_test_session_factory())

    _create_whitelist_for_user(client, admin_headers, user_headers)

    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "sync usage multi page"},
    )
    assert create_resp.status_code == 201
    item = client.get(_api("/api-keys"), headers=user_headers).json()["items"][0]
    key_id = item["id"]
    key_alias = item["key_alias"]
    sync_now = datetime.now(UTC).replace(microsecond=0)
    first_page_log_time = datetime(2026, 6, 8, 2, 0, 0, tzinfo=UTC)
    second_page_log_time = datetime(2026, 6, 8, 3, 0, 0, tzinfo=UTC)
    budget_reset_at = sync_now + timedelta(days=1)

    class _FakeProviderClient:
        def list_spend_logs(self, query: dict) -> dict:
            assert query["key_alias"] == key_alias
            if query["page"] == 1:
                return {
                    "data": [
                        {
                            "status": "success",
                            "spend": 0.25,
                            "prompt_tokens": 80,
                            "completion_tokens": 20,
                            "total_tokens": 100,
                            "startTime": first_page_log_time.isoformat(),
                            "endTime": first_page_log_time.isoformat(),
                        }
                    ],
                    "total": 2,
                    "page": 1,
                    "page_size": 100,
                    "total_pages": 2,
                    "budget_reset_at": budget_reset_at.isoformat(),
                }
            return {
                "data": [
                    {
                        "status": "success",
                        "spend": 0.75,
                        "prompt_tokens": 120,
                        "completion_tokens": 30,
                        "total_tokens": 150,
                        "startTime": second_page_log_time.isoformat(),
                        "endTime": second_page_log_time.isoformat(),
                    }
                ],
                "total": 2,
                "page": 2,
                "page_size": 100,
                "total_pages": 2,
                "budget_reset_at": budget_reset_at.isoformat(),
            }

    monkeypatch.setattr(sync_api_key_usage, "ProviderClient", lambda: _FakeProviderClient())
    monkeypatch.setattr(sync_api_key_usage, "_now_utc", lambda: sync_now)

    assert sync_api_key_usage.run_once(batch_size=100, dry_run=False) == 1

    rows = _fetch_usage_snapshot_rows(key_id)
    assert len(rows) == 1
    assert float(rows[0]["spend"]) == 1.0
    assert rows[0]["prompt_tokens"] == 200
    assert rows[0]["completion_tokens"] == 50
    assert rows[0]["total_tokens"] == 250

    listed = client.get(_api("/api-keys"), headers=user_headers)
    assert listed.status_code == 200
    assert listed.json()["items"][0]["usage_summary"]["spend"] == 1.0
    assert listed.json()["items"][0]["usage_summary"]["prompt_tokens"] == 200
    assert listed.json()["items"][0]["usage_summary"]["completion_tokens"] == 50
    assert listed.json()["items"][0]["usage_summary"]["total_tokens"] == 250


def test_usage_sync_script_processes_all_active_keys_across_batches(client, admin_headers, user_headers, monkeypatch):
    from scripts import sync_api_key_usage

    monkeypatch.setattr("scripts.sync_api_key_usage.SessionLocal", get_test_session_factory())
    _create_whitelist_for_user(client, admin_headers, user_headers)

    created_keys: list[tuple[str, str]] = []
    for index in range(3):
        create_resp = client.post(
            _api("/api-keys/applications"),
            headers=user_headers,
            json={"application_date": str(date.today()), "duration_days": 30, "purpose": f"batch-{index}"},
        )
        assert create_resp.status_code == 201

    listed = client.get(_api("/api-keys"), headers=user_headers).json()["items"]
    for item in listed:
        created_keys.append((item["id"], item["key_alias"]))

    sync_now = datetime(2026, 6, 18, 4, 0, 0, tzinfo=UTC)
    budget_reset_at = sync_now + timedelta(days=1)
    call_aliases: list[str] = []

    class _FakeProviderClient:
        def list_spend_logs(self, query: dict) -> dict:
            call_aliases.append(query["key_alias"])
            return {
                "data": [
                    {
                        "status": "success",
                        "spend": 0.2,
                        "prompt_tokens": 20,
                        "completion_tokens": 10,
                        "total_tokens": 30,
                        "startTime": sync_now.isoformat(),
                        "endTime": sync_now.isoformat(),
                    }
                ],
                "total": 1,
                "page": 1,
                "page_size": 100,
                "total_pages": 1,
                "budget_reset_at": budget_reset_at.isoformat(),
            }

    monkeypatch.setattr(sync_api_key_usage, "ProviderClient", lambda: _FakeProviderClient())
    monkeypatch.setattr(sync_api_key_usage, "_now_utc", lambda: sync_now)

    assert sync_api_key_usage.run_once(batch_size=2, dry_run=False) == 3

    assert sorted(call_aliases) == sorted([key_alias for _, key_alias in created_keys])
    for key_id, _ in created_keys:
        key_row = _fetch_key_row(key_id)
        assert key_row["usage_synced_at"].replace(tzinfo=UTC) == sync_now
        assert key_row["usage_total_tokens"] == 30


def test_usage_sync_script_repair_missing_cache_targets_only_incomplete_active_keys(client, admin_headers, user_headers, monkeypatch):
    from scripts import sync_api_key_usage

    monkeypatch.setattr("scripts.sync_api_key_usage.SessionLocal", get_test_session_factory())
    _create_whitelist_for_user(client, admin_headers, user_headers)

    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "repair target"},
    )
    assert create_resp.status_code == 201
    target_item = client.get(_api("/api-keys"), headers=user_headers).json()["items"][0]
    target_key_id = target_item["id"]
    target_key_alias = target_item["key_alias"]

    second_create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "already synced"},
    )
    assert second_create_resp.status_code == 201
    all_items = client.get(_api("/api-keys"), headers=user_headers).json()["items"]
    synced_item = next(item for item in all_items if item["id"] != target_key_id)
    synced_key_id = synced_item["id"]

    history_synced_at = datetime(2026, 6, 18, 4, 5, 0, tzinfo=UTC)
    with begin_connection() as conn:
        conn.execute(
            text(
                """
                INSERT INTO api_key_usage_snapshots (
                    id, api_key_id, bucket_granularity, bucket_start_utc, bucket_end_utc,
                    spend, prompt_tokens, completion_tokens, total_tokens, budget_reset_at, synced_at, created_at
                ) VALUES (
                    :id, :api_key_id, 'day', :bucket_start_utc, :bucket_end_utc,
                    :spend, :prompt_tokens, :completion_tokens, :total_tokens, :budget_reset_at, :synced_at, :created_at
                )
                """
            ),
            {
                "id": "repair-history-1",
                "api_key_id": target_key_id,
                "bucket_start_utc": datetime(2026, 6, 17, 16, 0, 0, tzinfo=UTC),
                "bucket_end_utc": datetime(2026, 6, 18, 16, 0, 0, tzinfo=UTC),
                "spend": 0.42,
                "prompt_tokens": 120,
                "completion_tokens": 30,
                "total_tokens": 150,
                "budget_reset_at": None,
                "synced_at": history_synced_at,
                "created_at": history_synced_at,
            },
        )
        conn.execute(
            text(
                """
                UPDATE api_keys
                SET usage_spend = :usage_spend,
                    usage_prompt_tokens = :usage_prompt_tokens,
                    usage_completion_tokens = :usage_completion_tokens,
                    usage_total_tokens = :usage_total_tokens,
                    usage_budget_reset_at = :usage_budget_reset_at,
                    usage_synced_at = :usage_synced_at
                WHERE id = :id
                """
            ),
            {
                "id": synced_key_id,
                "usage_spend": 0.55,
                "usage_prompt_tokens": 200,
                "usage_completion_tokens": 50,
                "usage_total_tokens": 250,
                "usage_budget_reset_at": datetime(2026, 6, 19, 8, 0, 0, tzinfo=UTC),
                "usage_synced_at": history_synced_at,
            },
        )
        conn.commit()

    sync_now = datetime(2026, 6, 18, 4, 10, 0, tzinfo=UTC)
    budget_reset_at = datetime(2026, 6, 19, 8, 0, 0, tzinfo=UTC)
    call_aliases: list[str] = []

    class _FakeProviderClient:
        def list_spend_logs(self, query: dict) -> dict:
            call_aliases.append(query["key_alias"])
            return {
                "data": [
                    {
                        "status": "success",
                        "spend": 0.42,
                        "prompt_tokens": 120,
                        "completion_tokens": 30,
                        "total_tokens": 150,
                        "startTime": sync_now.isoformat(),
                        "endTime": sync_now.isoformat(),
                    }
                ],
                "total": 1,
                "page": 1,
                "page_size": 100,
                "total_pages": 1,
                "budget_reset_at": budget_reset_at.isoformat(),
            }

    monkeypatch.setattr(sync_api_key_usage, "ProviderClient", lambda: _FakeProviderClient())
    monkeypatch.setattr(sync_api_key_usage, "_now_utc", lambda: sync_now)

    assert sync_api_key_usage.run_once(batch_size=1, dry_run=False, repair_missing_cache=True) == 1

    assert call_aliases == [target_key_alias]
    repaired_key = _fetch_key_row(target_key_id)
    assert repaired_key["usage_synced_at"].replace(tzinfo=UTC) == sync_now
    assert repaired_key["usage_total_tokens"] == 150
    untouched_key = _fetch_key_row(synced_key_id)
    assert untouched_key["usage_total_tokens"] == 250


def test_usage_sync_script_excludes_pre_reset_logs_from_current_cycle_cache(client, admin_headers, user_headers, monkeypatch):
    from scripts import sync_api_key_usage

    monkeypatch.setattr("scripts.sync_api_key_usage.SessionLocal", get_test_session_factory())

    try:
        _set_limit_strategy_config(
            budget_max_budget="1000",
            budget_duration="daily",
            rate_limit_tpm=10000,
            rate_limit_rpm=500,
            max_parallel_requests=0,
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
            json={"application_date": str(date.today()), "duration_days": 30, "purpose": "midday reset"},
        )
        assert create_resp.status_code == 201
        item = client.get(_api("/api-keys"), headers=user_headers).json()["items"][0]
        key_id = item["id"]
        key_alias = item["key_alias"]

        sync_now = datetime.now(UTC).replace(microsecond=0)
        local_today = sync_now.astimezone(sync_api_key_usage.TAIPEI_TZ).date()
        next_budget_reset_at = datetime.combine(
            local_today + timedelta(days=1),
            datetime.min.time(),
            tzinfo=sync_api_key_usage.TAIPEI_TZ,
        ).replace(hour=8).astimezone(UTC)
        cycle_start = next_budget_reset_at - timedelta(days=1)
        pre_reset_log_time = cycle_start - timedelta(minutes=30)
        post_reset_log_time = cycle_start + timedelta(hours=1)

        class _FakeProviderClient:
            def list_spend_logs(self, query: dict) -> dict:
                assert query["key_alias"] == key_alias
                return {
                    "data": [
                        {
                            "status": "success",
                            "spend": 0.4,
                            "prompt_tokens": 40,
                            "completion_tokens": 10,
                            "total_tokens": 50,
                            "startTime": pre_reset_log_time.isoformat(),
                            "endTime": pre_reset_log_time.isoformat(),
                        },
                        {
                            "status": "success",
                            "spend": 0.6,
                            "prompt_tokens": 60,
                            "completion_tokens": 15,
                            "total_tokens": 75,
                            "startTime": post_reset_log_time.isoformat(),
                            "endTime": post_reset_log_time.isoformat(),
                        },
                    ],
                    "total": 2,
                    "page": 1,
                    "page_size": 100,
                    "total_pages": 1,
                    "budget_reset_at": next_budget_reset_at.isoformat(),
                }

        monkeypatch.setattr(sync_api_key_usage, "ProviderClient", lambda: _FakeProviderClient())
        monkeypatch.setattr(sync_api_key_usage, "_now_utc", lambda: sync_now)

        assert sync_api_key_usage.run_once(batch_size=100, dry_run=False) == 1

        rows = _fetch_usage_snapshot_rows(key_id)
        assert len(rows) == 1
        assert float(rows[0]["spend"]) == 1.0
        assert rows[0]["total_tokens"] == 125

        listed = client.get(_api("/api-keys"), headers=user_headers)
        assert listed.status_code == 200
        assert listed.json()["items"][0]["usage_summary"]["spend"] == 0.6
        assert listed.json()["items"][0]["usage_summary"]["prompt_tokens"] == 60
        assert listed.json()["items"][0]["usage_summary"]["completion_tokens"] == 15
        assert listed.json()["items"][0]["usage_summary"]["total_tokens"] == 75
    finally:
        _set_limit_strategy_config(
            budget_max_budget="1000",
            budget_duration="monthly",
            rate_limit_tpm=10000,
            rate_limit_rpm=500,
            max_parallel_requests=0,
        )


def test_usage_sync_script_accepts_past_reset_boundary_and_keeps_same_day_post_reset_usage(
    client, admin_headers, user_headers, monkeypatch
):
    from scripts import sync_api_key_usage

    monkeypatch.setattr("scripts.sync_api_key_usage.SessionLocal", get_test_session_factory())

    try:
        _set_limit_strategy_config(
            budget_max_budget="1000",
            budget_duration="daily",
            rate_limit_tpm=10000,
            rate_limit_rpm=500,
            max_parallel_requests=0,
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
            json={"application_date": str(date.today()), "duration_days": 30, "purpose": "past reset boundary"},
        )
        assert create_resp.status_code == 201
        item = client.get(_api("/api-keys"), headers=user_headers).json()["items"][0]
        key_id = item["id"]
        key_alias = item["key_alias"]

        sync_now = datetime.now(UTC).replace(microsecond=0)
        local_today = sync_now.astimezone(sync_api_key_usage.TAIPEI_TZ).date()
        current_cycle_start = datetime.combine(
            local_today,
            datetime.min.time(),
            tzinfo=sync_api_key_usage.TAIPEI_TZ,
        ).replace(hour=8).astimezone(UTC)
        if current_cycle_start >= sync_now:
            current_cycle_start -= timedelta(days=1)
        next_budget_reset_at = current_cycle_start + timedelta(days=1)
        pre_reset_log_time = current_cycle_start - timedelta(minutes=30)
        post_reset_log_time = current_cycle_start + timedelta(hours=1)

        class _FakeProviderClient:
            def list_spend_logs(self, query: dict) -> dict:
                assert query["key_alias"] == key_alias
                return {
                    "data": [
                        {
                            "status": "success",
                            "spend": 0.4,
                            "prompt_tokens": 40,
                            "completion_tokens": 10,
                            "total_tokens": 50,
                            "startTime": pre_reset_log_time.isoformat(),
                            "endTime": pre_reset_log_time.isoformat(),
                        },
                        {
                            "status": "success",
                            "spend": 0.6,
                            "prompt_tokens": 60,
                            "completion_tokens": 15,
                            "total_tokens": 75,
                            "startTime": post_reset_log_time.isoformat(),
                            "endTime": post_reset_log_time.isoformat(),
                        },
                    ],
                    "total": 2,
                    "page": 1,
                    "page_size": 100,
                    "total_pages": 1,
                    "budget_reset_at": current_cycle_start.isoformat(),
                }

        monkeypatch.setattr(sync_api_key_usage, "ProviderClient", lambda: _FakeProviderClient())
        monkeypatch.setattr(sync_api_key_usage, "_now_utc", lambda: sync_now)

        assert sync_api_key_usage.run_once(batch_size=100, dry_run=False) == 1

        key_row = _fetch_key_row(key_id)
        assert key_row["usage_budget_reset_at"].replace(tzinfo=UTC) == next_budget_reset_at

        listed = client.get(_api("/api-keys"), headers=user_headers)
        assert listed.status_code == 200
        assert listed.json()["items"][0]["usage_summary"]["spend"] == 0.6
        assert listed.json()["items"][0]["usage_summary"]["prompt_tokens"] == 60
        assert listed.json()["items"][0]["usage_summary"]["completion_tokens"] == 15
        assert listed.json()["items"][0]["usage_summary"]["total_tokens"] == 75
    finally:
        _set_limit_strategy_config(
            budget_max_budget="1000",
            budget_duration="monthly",
            rate_limit_tpm=10000,
            rate_limit_rpm=500,
            max_parallel_requests=0,
        )


def test_usage_sync_script_writes_zero_current_cycle_cache_when_boundary_known(client, admin_headers, user_headers, monkeypatch):
    from scripts import sync_api_key_usage

    monkeypatch.setattr("scripts.sync_api_key_usage.SessionLocal", get_test_session_factory())

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
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "zero cycle"},
    )
    assert create_resp.status_code == 201
    item = client.get(_api("/api-keys"), headers=user_headers).json()["items"][0]
    key_alias = item["key_alias"]
    sync_now = datetime.now(UTC).replace(microsecond=0)
    next_budget_reset_at = sync_now + timedelta(days=7)

    class _FakeProviderClient:
        def list_spend_logs(self, query: dict) -> dict:
            assert query["key_alias"] == key_alias
            return {
                "data": [],
                "total": 0,
                "page": 1,
                "page_size": 100,
                "total_pages": 1,
                "budget_reset_at": next_budget_reset_at.isoformat(),
            }

    monkeypatch.setattr(sync_api_key_usage, "ProviderClient", lambda: _FakeProviderClient())
    monkeypatch.setattr(sync_api_key_usage, "_now_utc", lambda: sync_now)

    assert sync_api_key_usage.run_once(batch_size=100, dry_run=False) == 1

    listed = client.get(_api("/api-keys"), headers=user_headers)
    assert listed.status_code == 200
    assert listed.json()["items"][0]["usage_summary"]["spend"] == 0.0
    assert listed.json()["items"][0]["usage_summary"]["prompt_tokens"] == 0
    assert listed.json()["items"][0]["usage_summary"]["completion_tokens"] == 0
    assert listed.json()["items"][0]["usage_summary"]["total_tokens"] == 0


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


def test_usage_sync_script_skips_key_when_provider_paging_metadata_is_invalid(
    client, admin_headers, user_headers, monkeypatch, caplog
):
    from scripts import sync_api_key_usage

    monkeypatch.setattr("scripts.sync_api_key_usage.SessionLocal", get_test_session_factory())

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
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "invalid paging metadata"},
    )
    assert create_resp.status_code == 201
    item = client.get(_api("/api-keys"), headers=user_headers).json()["items"][0]
    key_id = item["id"]
    key_alias = item["key_alias"]
    sync_now = datetime(2026, 6, 8, 12, 34, 56, tzinfo=UTC)

    class _FakeProviderClient:
        def list_spend_logs(self, query: dict) -> dict:
            assert query["key_alias"] == key_alias
            return {
                "data": [
                    {
                        "status": "success",
                        "spend": 0.25,
                        "prompt_tokens": 80,
                        "completion_tokens": 20,
                        "total_tokens": 100,
                        "startTime": sync_now.isoformat(),
                        "endTime": sync_now.isoformat(),
                    }
                ],
                "total": 1,
                "page": 2,
                "page_size": 100,
                "total_pages": 1,
                "budget_reset_at": (sync_now + timedelta(days=1)).isoformat(),
            }

    monkeypatch.setattr(sync_api_key_usage, "ProviderClient", lambda: _FakeProviderClient())
    monkeypatch.setattr(sync_api_key_usage, "_now_utc", lambda: sync_now)

    logger = sync_api_key_usage.logging.getLogger("test_usage_sync_invalid_paging")
    logger.handlers = []
    logger.propagate = True

    with caplog.at_level("WARNING"):
        assert sync_api_key_usage.run_once(batch_size=100, dry_run=False, logger=logger) == 0

    assert _fetch_usage_snapshot_rows(key_id) == []
    key_row = _fetch_key_row(key_id)
    assert key_row["usage_budget_reset_at"] is None
    assert key_row["usage_synced_at"] is None
    assert "unexpected page" in caplog.text

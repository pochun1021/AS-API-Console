import logging
from types import SimpleNamespace
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.services.api_keys_service import (
    _extended_terms,
    _provider_total_days_for_expiration,
)
from db.repositories.types import AuthIdentity
from tests.api_keys_test_utils import (
    _assert_utc_datetime_string,
    _create_whitelist,
    _fetch_application_row,
    _fetch_application_row_for_key,
    _fetch_expiration_notice_rows,
    _fetch_key_row,
    _fetch_key_notice_state,
    _fetch_key_status_row,
    _insert_key_usage_snapshot_history,
    _set_application_limits,
    _set_expiration_notice_sent_at,
    _set_key_expires_at_offset_days,
    _set_key_expires_at_past,
    _set_key_owner_snapshot,
    _set_key_secret_material,
    _set_key_usage_snapshot,
    _set_limit_strategy_config,
)
from tests.conftest import api_path as _api, build_headers


def _expected_budget_reset_at(reference_at: datetime, duration: str) -> str:
    if reference_at.tzinfo is None:
        reference_at = reference_at.replace(tzinfo=UTC)
    reference_local = reference_at.astimezone(ZoneInfo("Asia/Taipei"))
    days = {"daily": 1, "weekly": 7, "monthly": 30}[duration]
    reset_local = datetime.combine(
        reference_local.date() + timedelta(days=days),
        datetime.min.time(),
        tzinfo=ZoneInfo("Asia/Taipei"),
    ).replace(hour=8)
    return reset_local.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _expected_rolled_budget_reset_at(reference_at: datetime, duration: str, *, now: datetime | None = None) -> str:
    if reference_at.tzinfo is None:
        reference_at = reference_at.replace(tzinfo=UTC)
    current_time = (now or datetime.now(UTC)).replace(microsecond=0)
    step_days = {"daily": 1, "weekly": 7, "monthly": 30}[duration]
    rolled = reference_at
    while rolled <= current_time:
        rolled += timedelta(days=step_days)
    return rolled.isoformat().replace("+00:00", "Z")


def test_extend_resets_application_date_for_new_effective_window():
    issued_at = datetime(2026, 6, 1, 0, 30, 0, tzinfo=UTC)
    now = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)

    next_application_date, extended_expires_at = _extended_terms(
        issued_at=issued_at,
        original_duration_days=30,
        now=now,
    )
    provider_duration_days = _provider_total_days_for_expiration(
        application_date=next_application_date,
        expires_at=extended_expires_at,
    )

    assert next_application_date == date(2026, 6, 10)
    assert extended_expires_at == datetime(2026, 7, 10, 0, 30, 0, tzinfo=UTC)
    assert provider_duration_days == 30


def test_calc_expiration_uses_fixed_day_duration():
    from app.services.api_keys_service import _calc_expiration

    issued_at = datetime(2026, 7, 8, 10, 30, 0, tzinfo=UTC)

    assert _calc_expiration(issued_at, 30) == datetime(2026, 8, 7, 10, 30, 0, tzinfo=UTC)
    assert _calc_expiration(issued_at, 180) == datetime(2027, 1, 4, 10, 30, 0, tzinfo=UTC)
    assert _calc_expiration(issued_at, 360) == datetime(2027, 7, 3, 10, 30, 0, tzinfo=UTC)


def test_application_success_and_no_plaintext_in_queries(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])

    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "test"},
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["api_key_plaintext"].startswith("AS-")
    _assert_utc_datetime_string(body["application"]["issued_at"])
    _assert_utc_datetime_string(body["application"]["expires_at"])
    application = _fetch_application_row(body["application"]["id"])
    assert application["account"] == user_headers["x-account"]
    assert application["sysid"] == int(user_headers["x-sysid"])
    assert application["is_proxy_submission"] in {0, False}
    assert application["proxy_operator_account"] is None
    issued_at = datetime.fromisoformat(body["application"]["issued_at"].replace("Z", "+00:00"))
    expires_at = datetime.fromisoformat(body["application"]["expires_at"].replace("Z", "+00:00"))
    assert expires_at - issued_at == timedelta(days=30)

    list_resp = client.get(_api("/api-keys"), headers=user_headers)
    assert list_resp.status_code == 200
    item = list_resp.json()["items"][0]
    assert "api_key_plaintext" not in item
    assert "key_prefix" not in item
    assert item["masked_key"].startswith("AS-...")
    assert item["key_alias"] == f"for_{user_headers['x-account']}"
    assert len(item["masked_key"]) == 10
    assert "expiration_notice_sent_at" in item
    assert "extend_eligible" in item
    assert item["usage_summary"] == {
        "spend": None,
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
        "max_budget": 1000.0,
        "remaining_budget": None,
        "tpm_limit": 10000,
        "rpm_limit": 500,
        "max_parallel_requests": 0,
        "budget_reset_at": None,
        "synced_at": None,
    }
    _assert_utc_datetime_string(item["expires_at"])


def test_application_not_live_blocks_user_submission(client, admin_headers, user_headers, monkeypatch):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    get_settings.cache_clear()
    settings = get_settings().model_copy(
        update={"api_key_application_go_live_at": datetime(2099, 6, 30, 0, 0, tzinfo=ZoneInfo("Asia/Taipei"))}
    )
    monkeypatch.setattr("app.services.api_keys_service.get_settings", lambda: settings)

    resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "not live gate"},
    )

    assert resp.status_code == 403
    body = resp.json()
    assert body["error"]["code"] == "APPLICATION_NOT_LIVE"
    assert body["error"]["message"] == "application is not live yet"
    assert body["go_live_at"] == "2099-06-30T00:00:00+08:00"
    list_resp = client.get(_api("/api-keys"), headers=user_headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["items"] == []


def test_application_not_live_does_not_block_admin_submission(client, admin_headers, monkeypatch):
    get_settings.cache_clear()
    settings = get_settings().model_copy(
        update={"api_key_application_go_live_at": datetime(2099, 6, 30, 0, 0, tzinfo=ZoneInfo("Asia/Taipei"))}
    )
    monkeypatch.setattr("app.services.api_keys_service.get_settings", lambda: settings)

    resp = client.post(
        _api("/api-keys/applications"),
        headers=admin_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "admin still allowed"},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["application"]["account"] == admin_headers["x-account"]


def test_list_api_keys_returns_usage_summary(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])

    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "test"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user_headers).json()["items"][0]["id"]
    synced_at = datetime.now(UTC).replace(microsecond=0)
    budget_reset_at = synced_at + timedelta(days=7)
    _set_key_usage_snapshot(
        key_id,
        usage_spend="999.99",
        usage_prompt_tokens=999,
        usage_completion_tokens=999,
        usage_total_tokens=1998,
        usage_budget_reset_at=budget_reset_at,
        usage_synced_at=synced_at,
    )
    _insert_key_usage_snapshot_history(
        key_id,
        spend="850.25",
        budget_reset_at=budget_reset_at,
        synced_at=synced_at,
        bucket_granularity="day",
        bucket_start_utc=synced_at - timedelta(hours=12),
        bucket_end_utc=synced_at + timedelta(hours=12),
        prompt_tokens=1000,
        completion_tokens=500,
        total_tokens=1500,
    )

    listed = client.get(_api("/api-keys"), headers=user_headers)

    assert listed.status_code == 200
    item = listed.json()["items"][0]
    assert item["usage_summary"]["spend"] == 850.25
    assert item["usage_summary"]["prompt_tokens"] == 1000
    assert item["usage_summary"]["completion_tokens"] == 500
    assert item["usage_summary"]["total_tokens"] == 1500
    assert item["usage_summary"]["max_budget"] == 1000.0
    assert item["usage_summary"]["remaining_budget"] == 149.75
    assert item["usage_summary"]["tpm_limit"] == 10000
    assert item["usage_summary"]["rpm_limit"] == 500
    assert item["usage_summary"]["max_parallel_requests"] == 0
    _assert_utc_datetime_string(item["usage_summary"]["budget_reset_at"])
    _assert_utc_datetime_string(item["usage_summary"]["synced_at"])


def test_list_api_keys_zeroes_stale_previous_cycle_usage_after_reset(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])

    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "stale cycle"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user_headers).json()["items"][0]["id"]
    budget_reset_at = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=1)
    synced_at = budget_reset_at - timedelta(minutes=5)
    try:
        _set_limit_strategy_config(
            budget_max_budget="1000",
            budget_duration="monthly",
            rate_limit_tpm=10000,
            rate_limit_rpm=500,
            max_parallel_requests=0,
            updated_at=synced_at - timedelta(minutes=1),
        )
        _set_key_usage_snapshot(
            key_id,
            usage_spend="850.25",
            usage_prompt_tokens=1000,
            usage_completion_tokens=500,
            usage_total_tokens=1500,
            usage_budget_reset_at=budget_reset_at,
            usage_synced_at=synced_at,
        )

        listed = client.get(_api("/api-keys"), headers=user_headers)

        assert listed.status_code == 200
        item = listed.json()["items"][0]
        assert item["usage_summary"]["spend"] == 0.0
        assert item["usage_summary"]["prompt_tokens"] == 0
        assert item["usage_summary"]["completion_tokens"] == 0
        assert item["usage_summary"]["total_tokens"] == 0
        assert item["usage_summary"]["remaining_budget"] == 1000.0
        assert item["usage_summary"]["synced_at"] == synced_at.isoformat().replace("+00:00", "Z")
        assert item["usage_summary"]["budget_reset_at"] == budget_reset_at.isoformat().replace("+00:00", "Z")
    finally:
        _set_limit_strategy_config(
            budget_max_budget="1000",
            budget_duration="monthly",
            rate_limit_tpm=10000,
            rate_limit_rpm=500,
            max_parallel_requests=0,
        )


def test_list_api_keys_keeps_current_cycle_usage_after_reset_when_sync_is_fresh(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])

    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "fresh cycle"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user_headers).json()["items"][0]["id"]
    budget_reset_at = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=1)
    synced_at = budget_reset_at + timedelta(minutes=10)
    try:
        _set_limit_strategy_config(
            budget_max_budget="1000",
            budget_duration="monthly",
            rate_limit_tpm=10000,
            rate_limit_rpm=500,
            max_parallel_requests=0,
            updated_at=synced_at - timedelta(minutes=1),
        )
        _set_key_usage_snapshot(
            key_id,
            usage_spend="999.99",
            usage_prompt_tokens=999,
            usage_completion_tokens=999,
            usage_total_tokens=1998,
            usage_budget_reset_at=budget_reset_at,
            usage_synced_at=synced_at,
        )
        _insert_key_usage_snapshot_history(
            key_id,
            spend="25.50",
            budget_reset_at=budget_reset_at,
            synced_at=synced_at,
            bucket_granularity="day",
            bucket_start_utc=budget_reset_at - timedelta(hours=12),
            bucket_end_utc=budget_reset_at + timedelta(hours=12),
            prompt_tokens=80,
            completion_tokens=20,
            total_tokens=100,
        )

        listed = client.get(_api("/api-keys"), headers=user_headers)

        assert listed.status_code == 200
        item = listed.json()["items"][0]
        assert item["usage_summary"]["spend"] == 25.5
        assert item["usage_summary"]["prompt_tokens"] == 80
        assert item["usage_summary"]["completion_tokens"] == 20
        assert item["usage_summary"]["total_tokens"] == 100
        assert item["usage_summary"]["remaining_budget"] == 974.5
        assert item["usage_summary"]["budget_reset_at"] == budget_reset_at.isoformat().replace("+00:00", "Z")
    finally:
        _set_limit_strategy_config(
            budget_max_budget="1000",
            budget_duration="monthly",
            rate_limit_tpm=10000,
            rate_limit_rpm=500,
            max_parallel_requests=0,
        )


def test_build_usage_summary_keeps_values_when_provider_reset_missing():
    from app.services.api_keys_service import _build_usage_summary

    reference_now = datetime.now(UTC).replace(microsecond=0)
    key_created_at = reference_now - timedelta(days=3)
    synced_at = reference_now - timedelta(days=1, minutes=1)

    usage_summary = _build_usage_summary(
        max_budget_raw="1000",
        budget_duration="daily",
        key_created_at=key_created_at,
        config_updated_at=None,
        tpm_limit=10000,
        rpm_limit=500,
        max_parallel_requests=0,
        spend=123.45,
        prompt_tokens=123,
        completion_tokens=45,
        total_tokens=168,
        budget_reset_at=None,
        synced_at=synced_at,
    )

    assert usage_summary["spend"] == 123.45
    assert usage_summary["prompt_tokens"] == 123
    assert usage_summary["completion_tokens"] == 45
    assert usage_summary["total_tokens"] == 168
    assert usage_summary["remaining_budget"] == 876.55
    assert usage_summary["budget_reset_at"] is None


def test_build_usage_summary_returns_provider_budget_reset_at_without_rollover():
    from app.services.api_keys_service import _build_usage_summary

    reference_now = datetime.now(UTC).replace(microsecond=0)
    key_created_at = reference_now - timedelta(days=3)
    budget_reset_at = reference_now - timedelta(hours=12)
    synced_at = reference_now - timedelta(hours=1)

    usage_summary = _build_usage_summary(
        max_budget_raw="1000",
        budget_duration="daily",
        key_created_at=key_created_at,
        config_updated_at=None,
        tpm_limit=10000,
        rpm_limit=500,
        max_parallel_requests=0,
        spend=123.45,
        prompt_tokens=123,
        completion_tokens=45,
        total_tokens=168,
        budget_reset_at=budget_reset_at,
        synced_at=synced_at,
    )

    assert usage_summary["spend"] == 123.45
    assert usage_summary["prompt_tokens"] == 123
    assert usage_summary["completion_tokens"] == 45
    assert usage_summary["total_tokens"] == 168
    assert usage_summary["remaining_budget"] == 876.55
    assert usage_summary["budget_reset_at"] == budget_reset_at


def test_list_api_keys_uses_snapshot_history_over_api_keys_usage_cache(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])

    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "test"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user_headers).json()["items"][0]["id"]
    stale_synced_at = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=1)
    fresh_synced_at = stale_synced_at + timedelta(minutes=30)
    _set_key_usage_snapshot(
        key_id,
        usage_spend="999.99",
        usage_prompt_tokens=333,
        usage_completion_tokens=444,
        usage_total_tokens=777,
        usage_budget_reset_at=stale_synced_at + timedelta(days=7),
        usage_synced_at=stale_synced_at,
    )
    _insert_key_usage_snapshot_history(
        key_id,
        spend="12.34",
        budget_reset_at=fresh_synced_at + timedelta(days=7),
        synced_at=fresh_synced_at,
        bucket_granularity="day",
        bucket_start_utc=fresh_synced_at,
        bucket_end_utc=fresh_synced_at + timedelta(days=1),
        prompt_tokens=12,
        completion_tokens=22,
        total_tokens=34,
    )

    listed = client.get(_api("/api-keys"), headers=user_headers)

    assert listed.status_code == 200
    item = listed.json()["items"][0]
    assert item["usage_summary"]["spend"] == 12.34
    assert item["usage_summary"]["prompt_tokens"] == 12
    assert item["usage_summary"]["completion_tokens"] == 22
    assert item["usage_summary"]["total_tokens"] == 34
    assert item["usage_summary"]["remaining_budget"] == 987.66
    assert item["usage_summary"]["max_parallel_requests"] == 0
    _assert_utc_datetime_string(item["usage_summary"]["budget_reset_at"])
    _assert_utc_datetime_string(item["usage_summary"]["synced_at"])


def test_usage_series_returns_daily_buckets_in_taipei_calendar(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])

    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "usage series"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user_headers).json()["items"][0]["id"]
    bucket_start_utc = datetime(2026, 5, 31, 16, 0, 0, tzinfo=UTC)
    bucket_end_utc = datetime(2026, 6, 1, 16, 0, 0, tzinfo=UTC)
    synced_at = datetime(2026, 6, 2, 2, 0, 0, tzinfo=UTC)
    _insert_key_usage_snapshot_history(
        key_id,
        spend="1.25",
        budget_reset_at=synced_at + timedelta(days=7),
        synced_at=synced_at,
        bucket_granularity="day",
        bucket_start_utc=bucket_start_utc,
        bucket_end_utc=bucket_end_utc,
        prompt_tokens=1000,
        completion_tokens=500,
        total_tokens=1500,
    )

    resp = client.get(
        _api("/api-keys/usage-series?key_id={}&granularity=day&from=2026-06-01&to=2026-06-01".format(key_id)),
        headers=user_headers,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["key_id"] == key_id
    assert body["granularity"] == "day"
    assert body["from"] == "2026-06-01"
    assert body["to"] == "2026-06-01"
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["bucket_label"] == "2026-06-01"
    assert item["prompt_tokens"] == 1000
    assert item["completion_tokens"] == 500
    assert item["total_tokens"] == 1500
    assert item["spend"] == 1.25
    assert item["bucket_start"].startswith("2026-06-01T00:00:00")
    assert item["bucket_start"].endswith("+08:00")


def test_usage_series_returns_empty_items_without_zero_fill(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "usage series empty"},
    )
    key_id = client.get(_api("/api-keys"), headers=user_headers).json()["items"][0]["id"]

    resp = client.get(
        _api(f"/api-keys/usage-series?key_id={key_id}&granularity=day&from=2026-06-01&to=2026-06-30"),
        headers=user_headers,
    )

    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_usage_series_rejects_invalid_query_and_permissions(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    _create_whitelist(client, admin_headers, "3001")
    client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "mine"},
    )
    other_headers = build_headers(
        role="user",
        account="other.user",
        name="Other User",
        email="other@example.com",
        sysid="3001",
    )
    client.post(
        _api("/api-keys/applications"),
        headers=other_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "other"},
    )
    items = client.get(_api("/api-keys"), headers=admin_headers).json()["items"]
    own_key_id = next(item["id"] for item in items if item["owner_account"] == user_headers["x-account"])
    other_key_id = next(item["id"] for item in items if item["owner_account"] == "other.user")

    forbidden = client.get(
        _api(f"/api-keys/usage-series?key_id={other_key_id}&granularity=day&from=2026-06-01&to=2026-06-30"),
        headers=user_headers,
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "KEY_NOT_OWNED_BY_USER"

    missing = client.get(
        _api("/api-keys/usage-series?key_id=missing&granularity=day&from=2026-06-01&to=2026-06-30"),
        headers=admin_headers,
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "VALIDATION_ERROR"

    invalid_granularity = client.get(
        _api(f"/api-keys/usage-series?key_id={own_key_id}&granularity=hour&from=2026-06-01&to=2026-06-30"),
        headers=user_headers,
    )
    assert invalid_granularity.status_code == 422
    assert invalid_granularity.json()["error"]["code"] == "VALIDATION_ERROR"

    invalid_window = client.get(
        _api(f"/api-keys/usage-series?key_id={own_key_id}&granularity=day&from=2026-06-30&to=2026-06-01"),
        headers=user_headers,
    )
    assert invalid_window.status_code == 422
    assert invalid_window.json()["error"]["code"] == "VALIDATION_ERROR"


def test_usage_total_returns_aggregate_for_visible_keys(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    _create_whitelist(client, admin_headers, "3001")
    client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "mine-a"},
    )
    client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "mine-b"},
    )
    client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "mine-c-no-usage"},
    )
    other_headers = build_headers(
        role="user",
        account="other.user",
        name="Other User",
        email="other@example.com",
        sysid="3001",
    )
    client.post(
        _api("/api-keys/applications"),
        headers=other_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "other"},
    )
    items = client.get(_api("/api-keys"), headers=admin_headers).json()["items"]
    own_ids = [item["id"] for item in items if item["owner_account"] == user_headers["x-account"]]
    other_id = next(item["id"] for item in items if item["owner_account"] == "other.user")

    synced_at = datetime(2026, 6, 2, 2, 0, 0, tzinfo=UTC)
    _insert_key_usage_snapshot_history(
        own_ids[0],
        spend="1.25",
        budget_reset_at=synced_at + timedelta(days=7),
        synced_at=synced_at,
        bucket_granularity="day",
        bucket_start_utc=datetime(2026, 5, 31, 16, 0, 0, tzinfo=UTC),
        bucket_end_utc=datetime(2026, 6, 1, 16, 0, 0, tzinfo=UTC),
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
    )
    _insert_key_usage_snapshot_history(
        own_ids[1],
        spend="2.50",
        budget_reset_at=synced_at + timedelta(days=7),
        synced_at=synced_at,
        bucket_granularity="day",
        bucket_start_utc=datetime(2026, 6, 1, 16, 0, 0, tzinfo=UTC),
        bucket_end_utc=datetime(2026, 6, 2, 16, 0, 0, tzinfo=UTC),
        prompt_tokens=200,
        completion_tokens=100,
        total_tokens=300,
    )
    _insert_key_usage_snapshot_history(
        other_id,
        spend="3.75",
        budget_reset_at=synced_at + timedelta(days=7),
        synced_at=synced_at,
        bucket_granularity="day",
        bucket_start_utc=datetime(2026, 6, 2, 16, 0, 0, tzinfo=UTC),
        bucket_end_utc=datetime(2026, 6, 3, 16, 0, 0, tzinfo=UTC),
        prompt_tokens=400,
        completion_tokens=200,
        total_tokens=600,
    )

    user_resp = client.get(_api("/api-keys/usage-total"), headers=user_headers)
    assert user_resp.status_code == 200
    assert user_resp.json() == {
        "scope": "all_visible_keys",
        "prompt_tokens": 300,
        "completion_tokens": 150,
        "total_tokens": 450,
        "key_count": 3,
    }

    admin_resp = client.get(_api("/api-keys/usage-total"), headers=admin_headers)
    assert admin_resp.status_code == 200
    assert admin_resp.json() == {
        "scope": "all_visible_keys",
        "prompt_tokens": 700,
        "completion_tokens": 350,
        "total_tokens": 1050,
        "key_count": 4,
    }

    future_issued_resp = client.get(
        _api("/api-keys?issued_at_from=2999-01-01T00:00:00Z"),
        headers=admin_headers,
    )
    assert future_issued_resp.status_code == 200
    assert future_issued_resp.json()["total"] == 0


def test_list_api_keys_uses_current_limit_strategy_config_for_usage_limits(
    client, admin_headers, user_headers
):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])

    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "test"},
    )
    assert create_resp.status_code == 201

    try:
        _set_limit_strategy_config(
            budget_max_budget="1000",
            budget_duration="monthly",
            rate_limit_tpm=43210,
            rate_limit_rpm=321,
            max_parallel_requests=12,
        )

        listed = client.get(_api("/api-keys"), headers=user_headers)

        assert listed.status_code == 200
        item = listed.json()["items"][0]
        assert item["usage_summary"]["max_budget"] == 1000.0
        assert item["usage_summary"]["tpm_limit"] == 43210
        assert item["usage_summary"]["rpm_limit"] == 321
        assert item["usage_summary"]["max_parallel_requests"] == 12
        assert item["usage_summary"]["budget_reset_at"] is None

        snapshot_synced_at = datetime.now(UTC).replace(microsecond=0)
        _set_key_usage_snapshot(
            item["id"],
            usage_spend="850.25",
            usage_budget_reset_at=snapshot_synced_at + timedelta(days=7),
            usage_synced_at=snapshot_synced_at,
        )
        _insert_key_usage_snapshot_history(
            item["id"],
            spend="850.25",
            budget_reset_at=snapshot_synced_at + timedelta(days=7),
            synced_at=snapshot_synced_at,
            bucket_granularity="day",
            bucket_start_utc=snapshot_synced_at - timedelta(hours=12),
            bucket_end_utc=snapshot_synced_at + timedelta(hours=12),
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        _set_limit_strategy_config(
            budget_max_budget="2000",
            budget_duration="monthly",
            rate_limit_tpm=54321,
            rate_limit_rpm=654,
            max_parallel_requests=9,
            updated_at=snapshot_synced_at + timedelta(minutes=5),
        )

        refreshed = client.get(_api("/api-keys"), headers=user_headers)

        assert refreshed.status_code == 200
        refreshed_item = refreshed.json()["items"][0]
        assert refreshed_item["usage_summary"]["max_budget"] == 2000.0
        assert refreshed_item["usage_summary"]["remaining_budget"] == 1149.75
        assert refreshed_item["usage_summary"]["tpm_limit"] == 54321
        assert refreshed_item["usage_summary"]["rpm_limit"] == 654
        assert refreshed_item["usage_summary"]["max_parallel_requests"] == 9
        assert (
            refreshed_item["usage_summary"]["budget_reset_at"]
            == (snapshot_synced_at + timedelta(days=7)).isoformat().replace("+00:00", "Z")
        )
    finally:
        _set_limit_strategy_config(
            budget_max_budget="1000",
            budget_duration="monthly",
            rate_limit_tpm=10000,
            rate_limit_rpm=500,
            max_parallel_requests=0,
        )


def test_list_api_keys_unlimited_budget_zero_remaining(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])

    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "test"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user_headers).json()["items"][0]["id"]
    synced_at = datetime.now(UTC).replace(microsecond=0)
    _set_application_limits(key_id, max_budget="0")
    try:
        _set_limit_strategy_config(
            budget_max_budget="0",
            budget_duration="monthly",
            rate_limit_tpm=0,
            rate_limit_rpm=0,
            max_parallel_requests=0,
        )
        _set_key_usage_snapshot(
            key_id,
            usage_spend="9999.99",
            usage_budget_reset_at=synced_at + timedelta(days=7),
            usage_synced_at=synced_at,
        )
        _insert_key_usage_snapshot_history(
            key_id,
            spend="9999.99",
            budget_reset_at=synced_at + timedelta(days=7),
            synced_at=synced_at,
            bucket_granularity="day",
            bucket_start_utc=synced_at - timedelta(hours=12),
            bucket_end_utc=synced_at + timedelta(hours=12),
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
        )

        listed = client.get(_api("/api-keys"), headers=user_headers)

        assert listed.status_code == 200
        item = listed.json()["items"][0]
        assert item["usage_summary"] == {
            "spend": 9999.99,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "max_budget": 0.0,
            "remaining_budget": 0.0,
            "tpm_limit": 0,
            "rpm_limit": 0,
            "max_parallel_requests": 0,
            "budget_reset_at": (synced_at + timedelta(days=7)).isoformat().replace("+00:00", "Z"),
            "synced_at": synced_at.isoformat().replace("+00:00", "Z"),
        }
    finally:
        _set_limit_strategy_config(
            budget_max_budget="1000",
            budget_duration="monthly",
            rate_limit_tpm=10000,
            rate_limit_rpm=500,
            max_parallel_requests=0,
        )


def test_list_api_keys_uses_current_limit_strategy_window_for_cycle_aggregation(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])

    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "daily cycle window"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user_headers).json()["items"][0]["id"]
    synced_at = datetime(2026, 6, 18, 6, 0, 0, tzinfo=UTC)
    budget_reset_at = datetime(2026, 6, 19, 0, 0, 0, tzinfo=UTC)
    try:
        _set_key_usage_snapshot(
            key_id,
            usage_spend="777.77",
            usage_prompt_tokens=777,
            usage_completion_tokens=777,
            usage_total_tokens=1554,
            usage_budget_reset_at=budget_reset_at,
            usage_synced_at=synced_at,
        )
        _insert_key_usage_snapshot_history(
            key_id,
            spend="12.34",
            budget_reset_at=budget_reset_at,
            synced_at=synced_at,
            bucket_granularity="day",
            bucket_start_utc=datetime(2026, 6, 15, 16, 0, 0, tzinfo=UTC),
            bucket_end_utc=datetime(2026, 6, 16, 16, 0, 0, tzinfo=UTC),
            prompt_tokens=123,
            completion_tokens=45,
            total_tokens=168,
        )
        _set_limit_strategy_config(
            budget_max_budget="1000",
            budget_duration="daily",
            rate_limit_tpm=10000,
            rate_limit_rpm=500,
            max_parallel_requests=0,
            updated_at=synced_at,
        )

        listed = client.get(_api("/api-keys"), headers=user_headers)

        assert listed.status_code == 200
        item = listed.json()["items"][0]
        assert item["usage_summary"]["spend"] == 0.0
        assert item["usage_summary"]["prompt_tokens"] == 0
        assert item["usage_summary"]["completion_tokens"] == 0
        assert item["usage_summary"]["total_tokens"] == 0
        assert item["usage_summary"]["remaining_budget"] == 1000.0
        assert item["usage_summary"]["budget_reset_at"] == budget_reset_at.isoformat().replace("+00:00", "Z")
    finally:
        _set_limit_strategy_config(
            budget_max_budget="1000",
            budget_duration="monthly",
            rate_limit_tpm=10000,
            rate_limit_rpm=500,
            max_parallel_requests=0,
        )


def test_application_rejects_unsafe_purpose(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])

    resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "<script>alert(1)</script>"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert resp.json()["error"]["message"] == "purpose contains unsafe syntax"


def test_application_rejects_unsafe_proxy_account(client, admin_headers, monkeypatch):
    _create_whitelist(client, admin_headers, admin_headers["x-sysid"])

    monkeypatch.setattr(
        "app.services.directory_identity_service.DirectoryIdentityService.is_configured",
        lambda self: True,
    )

    resp = client.post(
        _api("/api-keys/applications"),
        headers=admin_headers,
        json={
            "application_date": str(date.today()),
            "duration_days": 30,
            "purpose": "normal purpose",
            "target_identity": {"account": "foo => bar"},
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert resp.json()["error"]["message"] == "target_identity.account contains unsafe syntax"


def test_application_rejects_non_whitelisted(client, user_headers):
    from app.services.persnl_soap_service import PersnlSoapService

    original_is_configured = PersnlSoapService.is_configured
    PersnlSoapService.is_configured = lambda self: False
    try:
        resp = client.post(
            _api("/api-keys/applications"),
            headers=user_headers,
            json={"application_date": str(date.today()), "duration_days": 30, "purpose": "test"},
        )
    finally:
        PersnlSoapService.is_configured = original_is_configured
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "APPLICANT_NOT_ELIGIBLE"


def test_application_rejects_missing_auth_headers_with_field_details(client, user_headers):
    _create_whitelist(client, admin_headers=build_headers(role="admin", account="admin", email="admin@example.com", sysid="1001"), sysid=user_headers["x-sysid"])
    invalid_headers = dict(user_headers)
    invalid_headers.pop("x-name")

    resp = client.post(
        _api("/api-keys/applications"),
        headers=invalid_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "test"},
    )

    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "x-name" in resp.json()["error"]["message"]


def test_application_rejects_non_numeric_sysid(client, user_headers):
    invalid_headers = build_headers(role="user", account="user1", email="user1@example.com", sysid="not-a-number")

    resp = client.post(
        _api("/api-keys/applications"),
        headers=invalid_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "test"},
    )

    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert resp.json()["error"]["message"] == "x-sysid must be numeric"


def test_application_rejects_blank_purpose(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])

    resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "   "},
    )

    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert resp.json()["error"]["message"] == "purpose is required"


def test_admin_can_submit_proxy_application_for_target_user(client, admin_headers, monkeypatch):
    target_sysid = 4001
    _create_whitelist(client, admin_headers, target_sysid)
    monkeypatch.setattr(
        "app.services.api_keys_service.DirectoryIdentityService.is_configured",
        lambda self: True,
    )
    monkeypatch.setattr(
        "app.services.api_keys_service.DirectoryIdentityService.resolve_by_account",
        lambda self, account: AuthIdentity(
            account="target.user",
            name="Target User",
            email="target.user@example.com",
            department="R&D",
            sysid=target_sysid,
        ),
    )

    resp = client.post(
        _api("/api-keys/applications"),
        headers=admin_headers,
        json={
            "application_date": str(date.today()),
            "duration_days": 30,
            "purpose": "admin proxy submit",
            "target_identity": {
                "account": "target.user",
            },
        },
    )
    assert resp.status_code == 201
    assert resp.json()["application"]["account"] == "target.user"
    application = _fetch_application_row(resp.json()["application"]["id"])
    assert application["account"] == "target.user"
    assert application["name"] == "Target User"
    assert application["email"] == "target.user@example.com"
    assert application["department"] == "R&D"
    assert application["sysid"] == target_sysid
    assert application["is_proxy_submission"] in {1, True}
    assert application["proxy_operator_account"] == admin_headers["x-account"]


def test_admin_proxy_application_validates_required_target_identity_fields(client, admin_headers):
    resp = client.post(
        _api("/api-keys/applications"),
        headers=admin_headers,
        json={
            "application_date": str(date.today()),
            "duration_days": 30,
            "purpose": "admin proxy submit",
            "target_identity": {
                "account": "",
            },
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_admin_proxy_application_target_account_not_found(client, admin_headers, monkeypatch):
    monkeypatch.setattr(
        "app.services.api_keys_service.DirectoryIdentityService.is_configured",
        lambda self: True,
    )

    from app.services.directory_identity_service import DirectoryLookupNotFoundError

    def _raise_not_found(self, account):
        raise DirectoryLookupNotFoundError("not found")

    monkeypatch.setattr(
        "app.services.api_keys_service.DirectoryIdentityService.resolve_by_account",
        _raise_not_found,
    )
    resp = client.post(
        _api("/api-keys/applications"),
        headers=admin_headers,
        json={
            "application_date": str(date.today()),
            "duration_days": 30,
            "purpose": "admin proxy submit",
            "target_identity": {"account": "missing.user"},
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_admin_proxy_application_directory_unavailable(client, admin_headers, monkeypatch):
    monkeypatch.setattr(
        "app.services.api_keys_service.DirectoryIdentityService.is_configured",
        lambda self: True,
    )

    from app.services.directory_identity_service import DirectoryLookupUnavailableError

    def _raise_unavailable(self, account):
        raise DirectoryLookupUnavailableError("timeout")

    monkeypatch.setattr(
        "app.services.api_keys_service.DirectoryIdentityService.resolve_by_account",
        _raise_unavailable,
    )
    resp = client.post(
        _api("/api-keys/applications"),
        headers=admin_headers,
        json={
            "application_date": str(date.today()),
            "duration_days": 30,
            "purpose": "admin proxy submit",
            "target_identity": {"account": "target.user"},
        },
    )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "SOAP_SERVICE_UNAVAILABLE"


def test_admin_proxy_application_target_account_not_unique(client, admin_headers, monkeypatch):
    monkeypatch.setattr(
        "app.services.api_keys_service.DirectoryIdentityService.is_configured",
        lambda self: True,
    )

    from app.services.directory_identity_service import DirectoryLookupNotUniqueError

    def _raise_not_unique(self, account):
        raise DirectoryLookupNotUniqueError("multiple accounts")

    monkeypatch.setattr(
        "app.services.api_keys_service.DirectoryIdentityService.resolve_by_account",
        _raise_not_unique,
    )
    resp = client.post(
        _api("/api-keys/applications"),
        headers=admin_headers,
        json={
            "application_date": str(date.today()),
            "duration_days": 30,
            "purpose": "admin proxy submit",
            "target_identity": {"account": "duplicated.user"},
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_application_provider_timeout_returns_503(client, admin_headers, user_headers, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    monkeypatch.setenv("PROVIDER_TEAM_ID", "team-001")
    get_settings.cache_clear()
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)

    def _raise_unavailable(self, payload):
        from app.services.provider_client import ProviderUnavailableError

        raise ProviderUnavailableError("provider unavailable")

    monkeypatch.setattr("app.services.provider_client.ProviderClient.generate_key", _raise_unavailable)

    try:
        resp = client.post(
            _api("/api-keys/applications"),
            headers=user_headers,
            json={"application_date": str(date.today()), "duration_days": 30, "purpose": "test notify failure"},
        )
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        monkeypatch.delenv("PROVIDER_TEAM_ID", raising=False)
        get_settings.cache_clear()


def test_application_external_provider_requires_team_id(client, admin_headers, user_headers, monkeypatch):
    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    monkeypatch.delenv("PROVIDER_TEAM_ID", raising=False)
    get_settings.cache_clear()
    settings = get_settings().model_copy(update={"provider_team_id": ""})
    monkeypatch.setattr("app.services.api_keys_service.get_settings", lambda: settings)
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)

    provider_called = {"count": 0}

    def _should_not_call_provider(self, payload):
        provider_called["count"] += 1
        raise AssertionError("provider should not be called when PROVIDER_TEAM_ID is missing")

    monkeypatch.setattr("app.services.provider_client.ProviderClient.generate_key", _should_not_call_provider)

    try:
        resp = client.post(
            _api("/api-keys/applications"),
            headers=user_headers,
            json={"application_date": str(date.today()), "duration_days": 30, "purpose": "missing team id"},
        )
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "PROVIDER_TEAM_ID_REQUIRED"
        assert provider_called["count"] == 0
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        get_settings.cache_clear()


def test_provider_payload_builder_uses_external_contract():
    from app.services.api_keys_service import ApiKeysService, IssuanceConfigValues
    from types import SimpleNamespace

    service = object.__new__(ApiKeysService)
    service.settings = SimpleNamespace(provider_team_id="team-001")

    payload = service._build_provider_payload(
        key_alias="for_user1",
        duration_days=180,
        config=IssuanceConfigValues(
            max_budget="1000",
            budget_duration="monthly",
            tpm_limit=10000,
            rpm_limit=500,
            max_parallel_requests=0,
        ),
    )

    assert payload == {
        "max_budget": 1000.0,
        "budget_duration": "30d",
        "duration": "180d",
        "tpm_limit": 10000,
        "rpm_limit": 500,
        "max_parallel_requests": None,
        "team_id": "team-001",
        "key_alias": "for_user1",
        "key_type": "llm_api",
    }


def test_provider_payload_builder_converts_zero_rate_limits_to_null():
    from app.services.api_keys_service import ApiKeysService, IssuanceConfigValues
    from types import SimpleNamespace

    service = object.__new__(ApiKeysService)
    service.settings = SimpleNamespace(provider_team_id="team-001")

    payload = service._build_provider_payload(
        key_alias="for_user1",
        duration_days=30,
        config=IssuanceConfigValues(
            max_budget="1000",
            budget_duration="monthly",
            tpm_limit=0,
            rpm_limit=0,
            max_parallel_requests=0,
        ),
    )

    assert payload["tpm_limit"] is None
    assert payload["rpm_limit"] is None
    assert payload["max_parallel_requests"] is None
    assert payload["team_id"] == "team-001"


def test_provider_update_payload_builder_converts_zero_parallel_limit_to_null():
    from app.services.api_keys_service import ApiKeysService, IssuanceConfigValues
    from types import SimpleNamespace

    service = object.__new__(ApiKeysService)
    service.settings = SimpleNamespace(provider_team_id="team-001")

    payload = service._build_provider_update_payload(
        plaintext="AS-old",
        duration_days=30,
        config=IssuanceConfigValues(
            max_budget="1000",
            budget_duration="monthly",
            tpm_limit=10000,
            rpm_limit=500,
            max_parallel_requests=0,
        ),
        key_alias="for_user1",
    )

    assert payload["max_parallel_requests"] is None
    assert payload["team_id"] == "team-001"


def test_prod_env_masks_and_stores_sk_prefix(client, admin_headers, user_headers, monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("ALLOW_HEADER_AUTH", "true")
    get_settings.cache_clear()

    try:
        _create_whitelist(client, admin_headers, user_headers["x-sysid"])
        create_resp = client.post(
            _api("/api-keys/applications"),
            headers=user_headers,
            json={"application_date": str(date.today()), "duration_days": 30, "purpose": "prod prefix"},
        )
        assert create_resp.status_code == 201
        assert create_resp.json()["api_key_plaintext"].startswith("sk-")

        key_id = client.get(_api("/api-keys"), headers=user_headers).json()["items"][0]["id"]
        listed = client.get(_api("/api-keys"), headers=user_headers).json()["items"][0]
        assert listed["masked_key"].startswith("sk-...")

        settings = get_settings()
        db_url = settings.test_database_url or settings.database_url
        engine = create_engine(db_url, future=True)
        with engine.begin() as conn:
            row = conn.execute(text("SELECT key_prefix FROM api_keys WHERE id = :key_id"), {"key_id": key_id}).first()
        assert row is not None
        assert row[0] == "sk-"
    finally:
        monkeypatch.delenv("ALLOW_HEADER_AUTH", raising=False)
        monkeypatch.setenv("APP_ENV", "test")
        get_settings.cache_clear()


def test_expiration_notice_mail_contains_expiration_and_extend_hint(monkeypatch):
    from asyncio import run as run_async

    from app.services.mail_service import MailService

    captured: dict = {}

    async def _fake_send_html(self, *, subject: str, recipients: list[str], body: str):
        captured["subject"] = subject
        captured["recipients"] = recipients
        captured["body"] = body

    monkeypatch.setattr("app.services.mail_service.MailService._send_html", _fake_send_html)

    service = MailService()
    expires_at = datetime(2026, 6, 30, 1, 2, 3, tzinfo=UTC)
    run_async(
        service.send_key_expiration_notice(
            to_email="user@example.com",
            owner_name="User One",
            days_before=7,
            expires_at=expires_at,
            app_domain="",
        )
    )

    assert (
        captured["subject"]
        == "[AS-ITS] API Key 將於 7 天後到期 / API Key Expiration Notice (7 Days Remaining)"
    )
    assert captured["recipients"] == ["user@example.com"]
    assert "將於 7 天後到期" in captured["body"]
    assert "到期時間：2026 年 6 月 30 日 09:02（UTC+8）" in captured["body"]
    assert "如需持續使用，請於到期前或到期後至系統進行展延（Extend）作業。" in captured["body"]
    assert "服務申請／展延網址：https://api.ascs.sinica.edu.tw/main/" in captured["body"]
    assert "線上服務台（上班時間）：https://its.sinica.edu.tw/online" in captured["body"]
    assert "電話（上班時間）：(02) 2789-8855" in captured["body"]
    assert "Dear User," in captured["body"]
    assert "This is a reminder that your API Key will expire in 7 days." in captured["body"]
    assert "Expiration Date and Time: June 30, 2026, 09:02 (UTC+8)" in captured["body"]
    assert "Application / Extension URL: https://api.ascs.sinica.edu.tw/main/" in captured["body"]
    assert "Online Service Desk (Business Hours): https://its.sinica.edu.tw/online" in captured["body"]
    assert "Phone (Business Hours): +886-2-2789-8855" in captured["body"]
    assert "The Department of Information Technology Services<br/>Academia Sinica" in captured["body"]
    assert "Asia/Taipei" not in captured["body"]
    assert "台灣時間" not in captured["body"]
    assert "password: 27898855" not in captured["body"]


def test_expiration_reminder_script_supports_multi_stage_and_keeps_first_notice_timestamp(
    client, admin_headers, user_headers, monkeypatch
):
    from scripts import send_expiration_reminders

    calls: list[dict] = []
    settings = get_settings()
    db_url = settings.test_database_url or settings.database_url
    reminder_engine = create_engine(db_url, future=True)
    monkeypatch.setattr(
        "scripts.send_expiration_reminders.SessionLocal",
        sessionmaker(bind=reminder_engine, autoflush=False, autocommit=False, class_=Session),
    )
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "multi stage reminder"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user_headers).json()["items"][0]["id"]

    _set_key_expires_at_offset_days(key_id, days=30)
    app = _fetch_application_row_for_key(key_id)
    expires_at = datetime.fromisoformat(str(app["expires_at"]).replace("Z", "+00:00"))

    async def _fake_notice(self, **kwargs):
        del self
        calls.append(kwargs)

    monkeypatch.setattr("app.services.mail_service.MailService.send_key_expiration_notice", _fake_notice)

    for notice_days_before in (30, 14, 7, 3, 1):
        candidate = send_expiration_reminders.ReminderCandidate(
            key_id=key_id,
            application_id=app["id"],
            owner_name=app["name"],
            email=app["email"],
            expires_at=expires_at,
            notice_days_before=notice_days_before,
        )
        assert send_expiration_reminders._send_candidate_notice(candidate=candidate, logger=logging.getLogger()) is True

    duplicate_candidate = send_expiration_reminders.ReminderCandidate(
        key_id=key_id,
        application_id=app["id"],
        owner_name=app["name"],
        email=app["email"],
        expires_at=expires_at,
        notice_days_before=7,
    )
    assert send_expiration_reminders._send_candidate_notice(
        candidate=duplicate_candidate, logger=logging.getLogger()
    ) is False

    assert [call["days_before"] for call in calls] == [30, 14, 7, 3, 1]
    notice_rows = _fetch_expiration_notice_rows(key_id)
    assert len(notice_rows) == 5
    assert {(row["notice_days_before"], row["status"]) for row in notice_rows} == {
        (30, "sent"),
        (14, "sent"),
        (7, "sent"),
        (3, "sent"),
        (1, "sent"),
    }
    key_notice_state = _fetch_key_notice_state(key_id)
    assert key_notice_state["expiration_notice_sent_at"] == notice_rows[0]["sent_at"]


def test_expiration_reminder_script_retries_failed_notice_and_stops_after_success(
    client, admin_headers, user_headers, monkeypatch
):
    from scripts import send_expiration_reminders

    settings = get_settings()
    db_url = settings.test_database_url or settings.database_url
    reminder_engine = create_engine(db_url, future=True)
    monkeypatch.setattr(
        "scripts.send_expiration_reminders.SessionLocal",
        sessionmaker(bind=reminder_engine, autoflush=False, autocommit=False, class_=Session),
    )
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "retry reminder"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user_headers).json()["items"][0]["id"]
    _set_key_expires_at_offset_days(key_id, days=14)

    attempts = {"count": 0}

    async def _flaky_notice(self, **kwargs):
        del self, kwargs
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("smtp down")

    monkeypatch.setattr("app.services.mail_service.MailService.send_key_expiration_notice", _flaky_notice)

    dry_processed, dry_sent = send_expiration_reminders.run_once(
        batch_size=100,
        dry_run=True,
        logger=logging.getLogger(),
    )
    failed_processed, failed_sent = send_expiration_reminders.run_once(
        batch_size=100,
        dry_run=False,
        logger=logging.getLogger(),
    )
    retry_processed, retry_sent = send_expiration_reminders.run_once(
        batch_size=100,
        dry_run=False,
        logger=logging.getLogger(),
    )
    final_processed, final_sent = send_expiration_reminders.run_once(
        batch_size=100,
        dry_run=False,
        logger=logging.getLogger(),
    )

    assert (dry_processed, dry_sent) == (1, 0)
    assert (failed_processed, failed_sent) == (1, 0)
    assert (retry_processed, retry_sent) == (1, 1)
    assert (final_processed, final_sent) == (0, 0)

    notice_rows = _fetch_expiration_notice_rows(key_id)
    assert len(notice_rows) == 2
    failed_row = next(row for row in notice_rows if row["status"] == "failed")
    sent_row = next(row for row in notice_rows if row["status"] == "sent")
    assert failed_row["notice_days_before"] == 14
    assert failed_row["error_message"] == "smtp down"
    assert sent_row["success_notice_days_before"] == 14
    assert _fetch_key_notice_state(key_id)["expiration_notice_sent_at"] == sent_row["sent_at"]


def test_application_success_for_research_eligible_without_whitelist(client, user_headers, monkeypatch):
    monkeypatch.setattr(
        "app.services.api_keys_service.LoginEligibilityService.is_eligible_by_sysid",
        lambda self, sysid: False,
    )
    monkeypatch.setattr(
        "app.services.api_keys_service.PersnlSoapService.is_configured",
        lambda self: True,
    )
    monkeypatch.setattr(
        "app.services.api_keys_service.PersnlSoapService.search_person_by_account",
        lambda self, account, on_job: [{"tCode": "A01"}],
    )
    monkeypatch.setattr(
        "app.services.api_keys_service.LoginEligibilityService.is_allowed_by_tcode",
        lambda self, tcode: True,
    )

    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "test"},
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["api_key_plaintext"].startswith("AS-")


def test_application_research_service_unavailable_returns_503_and_no_records(client, admin_headers, user_headers, monkeypatch):
    monkeypatch.setattr(
        "app.services.api_keys_service.LoginEligibilityService.is_eligible_by_sysid",
        lambda self, sysid: False,
    )
    monkeypatch.setattr(
        "app.services.api_keys_service.PersnlSoapService.is_configured",
        lambda self: True,
    )

    def _raise_unavailable(self, account, on_job):
        from app.services.persnl_soap_service import PersnlSoapUnavailableError

        raise PersnlSoapUnavailableError("timeout")

    monkeypatch.setattr(
        "app.services.api_keys_service.PersnlSoapService.search_person_by_account",
        _raise_unavailable,
    )

    before = client.get(_api("/api-keys"), headers=admin_headers).json()["total"]
    resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "test"},
    )
    after = client.get(_api("/api-keys"), headers=admin_headers).json()["total"]

    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "SOAP_SERVICE_UNAVAILABLE"
    assert before == after


def test_application_rejects_invalid_duration(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 2, "purpose": "test"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_DURATION_DAYS"


def test_application_rejects_future_date(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": "2999-01-01", "duration_days": 30, "purpose": "test"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_APPLICATION_DATE"


def test_pending_endpoints_removed(client, admin_headers, user_headers):
    forbidden_list = client.get(_api("/api-keys/applications/pending"), headers=user_headers)
    assert forbidden_list.status_code == 404

    pending_list = client.get(_api("/api-keys/applications/pending"), headers=admin_headers)
    assert pending_list.status_code == 404


def test_issue_pending_endpoint_removed(client, admin_headers):
    resp = client.post(_api("/api-keys/applications/dummy-id/issue"), headers=admin_headers)
    assert resp.status_code == 405


def test_issue_pending_application_does_not_send_issued_email(client, admin_headers, user_headers, monkeypatch):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "test issue mail"},
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["api_key_plaintext"].startswith("AS-")


def test_issue_pending_application_local_mode_does_not_call_provider(client, admin_headers, user_headers, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "local")
    get_settings.cache_clear()
    try:
        _create_whitelist(client, admin_headers, user_headers["x-sysid"])
        create_resp = client.post(
            _api("/api-keys/applications"),
            headers=user_headers,
            json={"application_date": str(date.today()), "duration_days": 30, "purpose": "local issue mode"},
        )
        assert create_resp.status_code == 201
        monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)

        def _raise_provider_should_not_be_called(self, payload):
            raise AssertionError("provider should not be called in local issuance mode")

        monkeypatch.setattr(
            "app.services.provider_client.ProviderClient.generate_key",
            _raise_provider_should_not_be_called,
        )
        assert create_resp.json()["api_key_plaintext"].startswith("AS-")
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        get_settings.cache_clear()


def test_revoke_permissions_and_status_checks(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    user2 = build_headers(role="user", account="user2", email="user2@example.com", sysid="2002")

    _create_whitelist(client, admin_headers, user1["x-sysid"])

    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user1,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "test", "max_budget": "1000", "budget_duration": "monthly"},
    )
    key_id = client.get(_api("/api-keys"), headers=user1).json()["items"][0]["id"]
    assert create_resp.status_code == 201

    not_owner = client.post(_api(f"/api-keys/{key_id}/revoke"), headers=user2)
    assert not_owner.status_code == 403
    assert not_owner.json()["error"]["code"] == "KEY_NOT_OWNED_BY_USER"

    first = client.post(_api(f"/api-keys/{key_id}/revoke"), headers=user1)
    assert first.status_code == 200
    assert first.json()["status"] == "revoked"

    second = client.post(_api(f"/api-keys/{key_id}/revoke"), headers=user1)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "KEY_NOT_ACTIVE"


def test_revoke_provider_unavailable_does_not_change_local_status(client, admin_headers, monkeypatch):
    from app.core.config import get_settings
    from app.services.provider_client import ProviderUnavailableError

    user = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "revoke provider fail"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user).json()["items"][0]["id"]

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    monkeypatch.setenv("PROVIDER_TEAM_ID", "team-001")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)
    monkeypatch.setattr(
        "app.services.provider_client.ProviderClient.delete_key",
        lambda self, payload: (_ for _ in ()).throw(ProviderUnavailableError("provider unavailable")),
    )
    try:
        resp = client.post(_api(f"/api-keys/{key_id}/revoke"), headers=user)
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"
        row = _fetch_key_status_row(key_id)
        assert row["key_status"] == "active"
        assert row["application_status"] == "active"
        assert row["revoked_at"] is None
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        monkeypatch.delenv("PROVIDER_TEAM_ID", raising=False)
        get_settings.cache_clear()


def test_provider_mutation_payloads_use_key_field_and_shared_contract(client, admin_headers, monkeypatch):
    from app.core.config import get_settings
    from app.services.provider_client import ProviderGenerateResult

    user = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "revoke payload"},
    )
    assert create_resp.status_code == 201
    created_plaintext = create_resp.json()["api_key_plaintext"]
    key_id = client.get(_api("/api-keys"), headers=user).json()["items"][0]["id"]
    captured_delete_payload: dict = {}
    captured_generate_payload: dict = {}
    captured_update_payload: dict = {}

    def _capture_delete_payload(self, payload):
        captured_delete_payload.update(payload)
        return SimpleNamespace(request_id=None, operation_id=None)

    def _capture_generate_payload(self, payload):
        captured_generate_payload.update(payload)
        return ProviderGenerateResult(key_plaintext="AS-renewedabcdefghijklmnopqrstuvwxyz")

    def _capture_update_payload(self, payload):
        captured_update_payload.update(payload)
        return SimpleNamespace(request_id=None, operation_id=None)

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    monkeypatch.setenv("PROVIDER_TEAM_ID", "team-001")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)
    monkeypatch.setattr("app.services.provider_client.ProviderClient.delete_key", _capture_delete_payload)
    monkeypatch.setattr("app.services.provider_client.ProviderClient.generate_key", _capture_generate_payload)
    monkeypatch.setattr("app.services.provider_client.ProviderClient.update_key", _capture_update_payload)
    try:
        revoke = client.post(_api(f"/api-keys/{key_id}/revoke"), headers=user)
        assert revoke.status_code == 200
        assert captured_delete_payload == {"keys": [created_plaintext]}

        renew = client.post(_api(f"/api-keys/{key_id}/renew"), headers=user)
        assert renew.status_code == 200
        renewed_key_id = renew.json()["id"]
        renewed_plaintext = renew.json()["api_key_plaintext"]
        renewed_application = _fetch_application_row_for_key(renewed_key_id)
        renewed_expires_at = datetime.fromisoformat(renew.json()["expires_at"].replace("Z", "+00:00"))
        assert "key" not in captured_generate_payload
        assert captured_generate_payload["duration"] == "30d"
        assert captured_generate_payload["key_alias"] == f"for_{user['x-account']}"
        assert captured_generate_payload["key_type"] == "llm_api"
        assert captured_generate_payload["team_id"] == "team-001"
        assert "models" not in captured_generate_payload
        assert "api_key_plaintext" not in captured_generate_payload

        _set_expiration_notice_sent_at(renewed_key_id, datetime.now(UTC))
        extend = client.post(_api(f"/api-keys/{renewed_key_id}/extend"), headers=user, json={})
        assert extend.status_code == 200
        assert captured_update_payload["key"] == renewed_plaintext
        renewed_issued_at = datetime.fromisoformat(str(renewed_application["issued_at"]).replace("Z", "+00:00"))
        if renewed_issued_at.tzinfo is None:
            renewed_issued_at = renewed_issued_at.replace(tzinfo=UTC)
        assert renewed_expires_at - renewed_issued_at == timedelta(days=30)
        assert captured_update_payload["duration"] == "30d"
        assert captured_update_payload["key_alias"] == f"for_{user['x-account']}"
        assert captured_update_payload["key_type"] == "llm_api"
        assert captured_update_payload["team_id"] == "team-001"
        assert "models" not in captured_update_payload
        assert "api_key_plaintext" not in captured_update_payload
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        monkeypatch.delenv("PROVIDER_TEAM_ID", raising=False)
        get_settings.cache_clear()


def test_extend_sends_latest_key_alias_to_provider(client, admin_headers, monkeypatch):
    from app.core.config import get_settings

    user = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "extend alias preservation"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user).json()["items"][0]["id"]

    admin_update = client.patch(
        _api(f"/api-keys/{key_id}"),
        headers=admin_headers,
        json={"key_alias": "custom_admin_alias"},
    )
    assert admin_update.status_code == 200

    _set_key_expires_at_offset_days(key_id, days=3)
    captured_update_payload: dict = {}

    def _capture_update_payload(self, payload):
        captured_update_payload.update(payload)
        return SimpleNamespace(request_id=None, operation_id=None)

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    monkeypatch.setenv("PROVIDER_TEAM_ID", "team-001")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)
    monkeypatch.setattr("app.services.provider_client.ProviderClient.update_key", _capture_update_payload)
    try:
        extend = client.post(_api(f"/api-keys/{key_id}/extend"), headers=user, json={})
        assert extend.status_code == 200
        assert captured_update_payload["key_alias"] == "custom_admin_alias"

        detail = client.get(_api(f"/api-keys/{key_id}"), headers=admin_headers)
        assert detail.status_code == 200
        assert detail.json()["key_alias"] == "custom_admin_alias"
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        monkeypatch.delenv("PROVIDER_TEAM_ID", raising=False)
        get_settings.cache_clear()


def test_extend_resets_effective_window_and_sends_original_duration_to_provider(client, admin_headers, monkeypatch):
    from app.core.config import get_settings

    user = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user["x-sysid"])
    application_date = date.today() - timedelta(days=9)
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user,
        json={"application_date": str(application_date), "duration_days": 30, "purpose": "extend original duration"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user).json()["items"][0]["id"]
    captured_update_payload: dict = {}

    def _capture_update_payload(self, payload):
        captured_update_payload.update(payload)
        return SimpleNamespace(request_id=None, operation_id=None)

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    monkeypatch.setenv("PROVIDER_TEAM_ID", "team-001")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)
    monkeypatch.setattr("app.services.provider_client.ProviderClient.update_key", _capture_update_payload)
    try:
        extend = client.post(_api(f"/api-keys/{key_id}/extend"), headers=user, json={})
        assert extend.status_code == 200
        updated_application = _fetch_application_row_for_key(key_id)
        expected_application_date = date.today()
        assert updated_application["application_date"] == expected_application_date
        assert updated_application["duration_days"] == 30
        assert captured_update_payload["duration"] == "30d"
        assert extend.json()["expires_at"].startswith(str(expected_application_date + timedelta(days=30)))
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        monkeypatch.delenv("PROVIDER_TEAM_ID", raising=False)
        get_settings.cache_clear()


def test_extend_expired_returns_key_not_extendable(client, admin_headers):
    user = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user["x-sysid"])
    original_application_date = date.today() - timedelta(days=40)
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user,
        json={"application_date": str(original_application_date), "duration_days": 30, "purpose": "extend expired reset"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user).json()["items"][0]["id"]
    _set_key_expires_at_past(key_id)
    extend = client.post(_api(f"/api-keys/{key_id}/extend"), headers=user, json={})
    assert extend.status_code == 409
    assert extend.json()["error"]["code"] == "KEY_NOT_EXTENDABLE"


def test_create_application_retries_key_alias_with_version_suffix(client, admin_headers, monkeypatch):
    from app.core.config import get_settings
    from app.services.provider_client import ProviderBadRequestError, ProviderGenerateResult

    user = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user["x-sysid"])
    attempted_aliases: list[str] = []

    def _generate_with_retry(self, payload):
        attempted_aliases.append(payload["key_alias"])
        if len(attempted_aliases) == 1:
            raise ProviderBadRequestError("provider rejected request: 400")
        return ProviderGenerateResult(key_plaintext="AS-generatedabcdefghijklmnopqrstuvwxyz")

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    monkeypatch.setenv("PROVIDER_TEAM_ID", "team-001")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)
    monkeypatch.setattr("app.services.provider_client.ProviderClient.generate_key", _generate_with_retry)
    try:
        create_resp = client.post(
            _api("/api-keys/applications"),
            headers=user,
            json={"application_date": str(date.today()), "duration_days": 30, "purpose": "retry alias"},
        )
        assert create_resp.status_code == 201
        assert attempted_aliases == [f"for_{user['x-account']}", f"for_{user['x-account']}_v2"]

        listed = client.get(_api("/api-keys"), headers=user)
        assert listed.status_code == 200
        assert listed.json()["items"][0]["key_alias"] == f"for_{user['x-account']}_v2"
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        monkeypatch.delenv("PROVIDER_TEAM_ID", raising=False)
        get_settings.cache_clear()


def test_renew_permissions_and_visibility(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    user2 = build_headers(role="user", account="user2", email="user2@example.com", sysid="2002")

    _create_whitelist(client, admin_headers, user1["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user1,
        json={"application_date": str(date.today()), "duration_days": 180, "purpose": "renew test"},
    )
    assert create_resp.status_code == 201
    source_id = client.get(_api("/api-keys"), headers=user1).json()["items"][0]["id"]
    revoke = client.post(_api(f"/api-keys/{source_id}/revoke"), headers=user1)
    assert revoke.status_code == 200

    not_owner = client.post(_api(f"/api-keys/{source_id}/renew"), headers=user2)
    assert not_owner.status_code == 403
    assert not_owner.json()["error"]["code"] == "KEY_NOT_OWNED_BY_USER"

    renew = client.post(_api(f"/api-keys/{source_id}/renew"), headers=user1)
    assert renew.status_code == 200
    body = renew.json()
    assert body["status"] == "active"
    assert body["renewed_from_key_id"] == source_id
    assert body["api_key_plaintext"].startswith("AS-")
    renewed_application = _fetch_application_row_for_key(body["id"])
    assert renewed_application["account"] == user1["x-account"]
    assert renewed_application["sysid"] == int(user1["x-sysid"])
    assert renewed_application["is_proxy_submission"] in {0, False}
    assert renewed_application["proxy_operator_account"] is None

    user_list = client.get(_api("/api-keys"), headers=user1)
    assert user_list.status_code == 200
    user_items = user_list.json()["items"]
    assert len(user_items) == 1
    assert user_items[0]["id"] == body["id"]
    assert user_items[0]["duration_days"] == 180

    admin_list = client.get(_api("/api-keys"), headers=admin_headers)
    assert admin_list.status_code == 200
    admin_ids = {item["id"] for item in admin_list.json()["items"]}
    assert source_id in admin_ids
    assert body["id"] in admin_ids

    duplicate = client.post(_api(f"/api-keys/{source_id}/renew"), headers=user1)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "KEY_ALREADY_RENEWED"


def test_renew_rejects_active_key(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "renew active"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user_headers).json()["items"][0]["id"]
    renew = client.post(_api(f"/api-keys/{key_id}/renew"), headers=user_headers)
    assert renew.status_code == 409
    assert renew.json()["error"]["code"] == "KEY_NOT_RENEWABLE"


def test_expired_is_visible_and_renewable_by_expires_at(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "expire-visible"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user_headers).json()["items"][0]["id"]
    _set_key_expires_at_past(key_id)

    listed = client.get(_api("/api-keys"), headers=user_headers)
    assert listed.status_code == 200
    assert listed.json()["items"][0]["status"] == "expired"
    _assert_utc_datetime_string(listed.json()["items"][0]["expires_at"])

    detail = client.get(_api(f"/api-keys/{key_id}"), headers=user_headers)
    assert detail.status_code == 200
    assert detail.json()["status"] == "expired"
    _assert_utc_datetime_string(detail.json()["created_at"])
    _assert_utc_datetime_string(detail.json()["expires_at"])

    renew = client.post(_api(f"/api-keys/{key_id}/renew"), headers=user_headers)
    assert renew.status_code == 200
    assert renew.json()["renewed_from_key_id"] == key_id
    assert renew.json()["status"] == "active"
    assert renew.json()["api_key_plaintext"]

def test_renew_expired_key_calls_provider_generate(client, admin_headers, user_headers, monkeypatch):
    from app.core.config import get_settings

    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "expired renew gate"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user_headers).json()["items"][0]["id"]
    _set_key_expires_at_past(key_id)

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    monkeypatch.setenv("PROVIDER_TEAM_ID", "team-001")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)

    generate_calls = {"count": 0}

    def _generate_key(self, payload):
        generate_calls["count"] += 1
        return SimpleNamespace(key_plaintext="AS-renewedabcdefghijklmnopqrstuvwxyz", request_id=None, operation_id=None)

    monkeypatch.setattr("app.services.provider_client.ProviderClient.generate_key", _generate_key)
    try:
        renew = client.post(_api(f"/api-keys/{key_id}/renew"), headers=user_headers)
        assert renew.status_code == 200
        assert renew.json()["renewed_from_key_id"] == key_id
        assert generate_calls["count"] == 1
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        monkeypatch.delenv("PROVIDER_TEAM_ID", raising=False)
        get_settings.cache_clear()


def test_extend_active_keys_anytime_for_user_and_admin_but_rejects_expired(client, admin_headers):
    user = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user["x-sysid"])
    original_application_date = str(date.today())
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user,
        json={"application_date": original_application_date, "duration_days": 30, "purpose": "extend near expiry gate"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user).json()["items"][0]["id"]
    _set_key_expires_at_offset_days(key_id, days=31)

    allowed = client.post(_api(f"/api-keys/{key_id}/extend"), headers=user, json={})
    assert allowed.status_code == 200
    assert allowed.json()["status"] == "active"
    _assert_utc_datetime_string(allowed.json()["expires_at"])
    assert _fetch_key_notice_state(key_id)["expiration_notice_sent_at"] is None
    active_extended = _fetch_application_row_for_key(key_id)
    active_application_date = str(date.today())
    assert str(active_extended["application_date"]) == active_application_date
    assert active_extended["original_duration_days"] == 30
    assert active_extended["duration_days"] == 30

    active_listed = client.get(_api("/api-keys"), headers=user)
    assert active_listed.status_code == 200
    assert active_listed.json()["items"][0]["application_date"] == active_application_date
    assert active_listed.json()["items"][0]["duration_days"] == 30

    active_detail = client.get(_api(f"/api-keys/{key_id}"), headers=user)
    assert active_detail.status_code == 200
    assert active_detail.json()["application_date"] == active_application_date
    assert active_detail.json()["duration_days"] == 30

    allowed_admin = client.post(_api(f"/api-keys/{key_id}/extend"), headers=admin_headers, json={})
    assert allowed_admin.status_code == 200
    assert allowed_admin.json()["status"] == "active"

    _set_key_expires_at_past(key_id)
    user_expired_rejected = client.post(_api(f"/api-keys/{key_id}/extend"), headers=user, json={})
    assert user_expired_rejected.status_code == 409
    assert user_expired_rejected.json()["error"]["code"] == "KEY_NOT_EXTENDABLE"

    admin_expired_rejected = client.post(_api(f"/api-keys/{key_id}/extend"), headers=admin_headers, json={})
    assert admin_expired_rejected.status_code == 409
    assert admin_expired_rejected.json()["error"]["code"] == "KEY_NOT_EXTENDABLE"


def test_extend_provider_unavailable_does_not_change_expiration(client, admin_headers, monkeypatch):
    from app.core.config import get_settings
    from app.services.provider_client import ProviderUnavailableError

    user = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "extend provider fail"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user).json()["items"][0]["id"]
    _set_key_expires_at_offset_days(key_id, days=14)
    before = _fetch_key_status_row(key_id)

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    monkeypatch.setenv("PROVIDER_TEAM_ID", "team-001")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)
    monkeypatch.setattr(
        "app.services.provider_client.ProviderClient.update_key",
        lambda self, payload: (_ for _ in ()).throw(ProviderUnavailableError("provider unavailable")),
    )
    try:
        resp = client.post(_api(f"/api-keys/{key_id}/extend"), headers=user, json={})
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"
        after = _fetch_key_status_row(key_id)
        assert after["key_status"] == before["key_status"]
        assert after["application_status"] == before["application_status"]
        assert after["expires_at"] == before["expires_at"]
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        monkeypatch.delenv("PROVIDER_TEAM_ID", raising=False)
        get_settings.cache_clear()


def test_provider_operations_require_secret_material_before_calling_provider(client, admin_headers, monkeypatch):
    from app.core.config import get_settings

    user = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user["x-sysid"])
    active_resp = client.post(
        _api("/api-keys/applications"),
        headers=user,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "missing secret active"},
    )
    assert active_resp.status_code == 201
    active_key_id = client.get(_api("/api-keys"), headers=user).json()["items"][0]["id"]
    _set_key_secret_material(active_key_id, key_ciphertext=None, key_kek_version=None)
    _set_key_expires_at_offset_days(active_key_id, days=14)

    revoked_resp = client.post(
        _api("/api-keys/applications"),
        headers=user,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "missing secret revoked"},
    )
    assert revoked_resp.status_code == 201
    key_items = client.get(_api("/api-keys"), headers=user).json()["items"]
    revoked_key_id = next(item["id"] for item in key_items if item["id"] != active_key_id)
    revoked = client.post(_api(f"/api-keys/{revoked_key_id}/revoke"), headers=user)
    assert revoked.status_code == 200
    _set_key_secret_material(revoked_key_id, key_ciphertext=None, key_kek_version=None)

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    monkeypatch.setenv("PROVIDER_TEAM_ID", "team-001")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)
    renew_calls = {"count": 0}

    def _should_not_call_provider(self, payload):
        raise AssertionError("provider should not be called without secret material")

    def _generate_without_secret_dependency(self, payload):
        renew_calls["count"] += 1
        return SimpleNamespace(key_plaintext="AS-renewedabcdefghijklmnopqrstuvwxyz", request_id=None, operation_id=None)

    monkeypatch.setattr("app.services.provider_client.ProviderClient.delete_key", _should_not_call_provider)
    monkeypatch.setattr("app.services.provider_client.ProviderClient.update_key", _should_not_call_provider)
    monkeypatch.setattr("app.services.provider_client.ProviderClient.generate_key", _generate_without_secret_dependency)
    try:
        revoke = client.post(_api(f"/api-keys/{active_key_id}/revoke"), headers=user)
        assert revoke.status_code == 409
        assert revoke.json()["error"]["code"] == "KEY_NOT_REVEALABLE"

        extend = client.post(_api(f"/api-keys/{active_key_id}/extend"), headers=user, json={})
        assert extend.status_code == 409
        assert extend.json()["error"]["code"] == "KEY_NOT_REVEALABLE"

        renew = client.post(_api(f"/api-keys/{revoked_key_id}/renew"), headers=user)
        assert renew.status_code == 200
        assert renew_calls["count"] == 1
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        monkeypatch.delenv("PROVIDER_TEAM_ID", raising=False)
        get_settings.cache_clear()


def test_renew_provider_unavailable_returns_503(client, admin_headers, monkeypatch):
    from app.core.config import get_settings
    from app.services.provider_client import ProviderUnavailableError

    user = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "renew pending"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user).json()["items"][0]["id"]
    client.post(_api(f"/api-keys/{key_id}/revoke"), headers=user)

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    monkeypatch.setenv("PROVIDER_TEAM_ID", "team-001")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)
    monkeypatch.setattr(
        "app.services.provider_client.ProviderClient.generate_key",
        lambda self, payload: (_ for _ in ()).throw(ProviderUnavailableError("provider unavailable")),
    )
    try:
        renew = client.post(_api(f"/api-keys/{key_id}/renew"), headers=user)
        assert renew.status_code == 503
        assert renew.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        monkeypatch.delenv("PROVIDER_TEAM_ID", raising=False)
        get_settings.cache_clear()


def test_application_provider_422_maps_to_validation_error(client, admin_headers, user_headers, monkeypatch):
    from app.core.config import get_settings
    from app.services.provider_client import ProviderBadRequestError

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    monkeypatch.setenv("PROVIDER_TEAM_ID", "team-001")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.api_keys_service.LoginEligibilityService.is_eligible_by_sysid", lambda self, sysid: True)
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)
    monkeypatch.setattr(
        "app.services.provider_client.ProviderClient.generate_key",
        lambda self, payload: (_ for _ in ()).throw(ProviderBadRequestError("body.duration: invalid duration")),
    )
    try:
        resp = client.post(
            _api("/api-keys/applications"),
            headers=user_headers,
            json={"application_date": str(date.today()), "duration_days": 180, "purpose": "provider-422"},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        monkeypatch.delenv("PROVIDER_TEAM_ID", raising=False)
        get_settings.cache_clear()


def test_admin_can_list_global_keys(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    user2 = build_headers(role="user", account="user2", email="user2@example.com", sysid="2002")
    _create_whitelist(client, admin_headers, user1["x-sysid"])
    _create_whitelist(client, admin_headers, user2["x-sysid"])

    resp1 = client.post(
        _api("/api-keys/applications"),
        headers=user1,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "u1", "max_budget": "1000", "budget_duration": "monthly"},
    )
    resp2 = client.post(
        _api("/api-keys/applications"),
        headers=user2,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "u2", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert resp1.status_code == 201
    assert resp2.status_code == 201
    admin_list = client.get(_api("/api-keys"), headers=admin_headers)
    assert admin_list.status_code == 200
    owners = {item["owner_account"] for item in admin_list.json()["items"]}
    assert "user1" in owners
    assert "user2" in owners


def test_admin_can_filter_key_list_by_owner_status_and_date(client, admin_headers):
    user1 = build_headers(role="user", account="ktu", email="ktu@example.com", sysid="2001", name="KTU")
    user2 = build_headers(role="user", account="user2", email="user2@example.com", sysid="2002", name="Other User")
    _create_whitelist(client, admin_headers, user1["x-sysid"])
    _create_whitelist(client, admin_headers, user2["x-sysid"])

    resp1 = client.post(
        _api("/api-keys/applications"),
        headers=user1,
        json={"application_date": "2026-05-01", "duration_days": 30, "purpose": "u1", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert resp1.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user1).json()["items"][0]["id"]
    revoke = client.post(_api(f"/api-keys/{key_id}/revoke"), headers=user1)
    assert revoke.status_code == 200

    resp2 = client.post(
        _api("/api-keys/applications"),
        headers=user1,
        json={"application_date": "2026-05-10", "duration_days": 30, "purpose": "u1-2", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert resp2.status_code == 201
    latest_user1_key_id = client.get(_api("/api-keys?sort_by=application_date&sort_dir=desc"), headers=user1).json()["items"][0]["id"]
    _set_key_owner_snapshot(latest_user1_key_id, name="尤凱婷")

    resp3 = client.post(
        _api("/api-keys/applications"),
        headers=user2,
        json={"application_date": "2026-05-03", "duration_days": 30, "purpose": "u2", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert resp3.status_code == 201

    filtered = client.get(
        _api(
            "/api-keys?owner_account=kt&owner_name=%E5%B0%A4&status=active"
            "&application_date_from=2026-05-05&application_date_to=2026-05-31"
        ),
        headers=admin_headers,
    )
    assert filtered.status_code == 200
    items = filtered.json()["items"]
    assert len(items) == 1
    assert items[0]["owner_account"] == "ktu"
    assert items[0]["owner_name"] == "尤凱婷"
    assert items[0]["status"] == "active"
    assert items[0]["application_date"] == "2026-05-10"


def test_admin_can_filter_key_list_by_key_alias_expires_and_sort(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="2301", name="User One")
    user2 = build_headers(role="user", account="user2", email="user2@example.com", sysid="2302", name="User Two")
    _create_whitelist(client, admin_headers, user1["x-sysid"])
    _create_whitelist(client, admin_headers, user2["x-sysid"])

    first = client.post(
        _api("/api-keys/applications"),
        headers=user1,
        json={"application_date": "2026-05-01", "duration_days": 30, "purpose": "u1", "max_budget": "1000", "budget_duration": "monthly"},
    )
    second = client.post(
        _api("/api-keys/applications"),
        headers=user2,
        json={"application_date": "2026-05-02", "duration_days": 30, "purpose": "u2", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert first.status_code == 201
    assert second.status_code == 201

    listed = client.get(_api("/api-keys"), headers=admin_headers)
    assert listed.status_code == 200
    key_ids = {item["owner_account"]: item["id"] for item in listed.json()["items"] if item["owner_account"] in {"user1", "user2"}}

    alias_update = client.patch(
        _api(f"/api-keys/{key_ids['user2']}"),
        headers=admin_headers,
        json={"key_alias": "custom_sort_alias"},
    )
    assert alias_update.status_code == 200

    expires_filtered = client.get(
        _api(
            "/api-keys?key_alias=sort_alias&expires_from=2026-05-31T00:00:00Z"
            "&expires_to=2026-12-31T23:59:59Z&sort_by=owner_account&sort_dir=asc"
        ),
        headers=admin_headers,
    )
    assert expires_filtered.status_code == 200
    body = expires_filtered.json()
    assert body["total"] == 1
    assert body["items"][0]["owner_account"] == "user2"
    assert body["items"][0]["key_alias"] == "custom_sort_alias"


def test_list_api_keys_total_is_full_match_count_not_page_size(client, admin_headers):
    user = build_headers(role="user", account="pager", email="pager@example.com", sysid="2201")
    _create_whitelist(client, admin_headers, user["x-sysid"])

    for i in range(3):
        resp = client.post(
            _api("/api-keys/applications"),
            headers=user,
            json={
                "application_date": str(date.today()),
                "duration_days": 30,
                "purpose": f"pager-{i}",
                "max_budget": "1000",
                "budget_duration": "monthly",
            },
        )
        assert resp.status_code == 201

    page1 = client.get(_api("/api-keys?page=1&page_size=1"), headers=user)
    page2 = client.get(_api("/api-keys?page=2&page_size=1"), headers=user)
    assert page1.status_code == 200
    assert page2.status_code == 200
    assert len(page1.json()["items"]) == 1
    assert len(page2.json()["items"]) == 1
    assert page1.json()["total"] == 3
    assert page2.json()["total"] == 3


def test_list_api_keys_accepts_page_and_page_size_query_params(client, admin_headers):
    user = build_headers(role="user", account="pagequery", email="pagequery@example.com", sysid="2202")
    _create_whitelist(client, admin_headers, user["x-sysid"])
    resp = client.post(
        _api("/api-keys/applications"),
        headers=user,
        json={
            "application_date": str(date.today()),
            "duration_days": 30,
            "purpose": "page-query",
            "max_budget": "1000",
            "budget_duration": "monthly",
        },
    )
    assert resp.status_code == 201

    listed = client.get(_api("/api-keys?page=1&page_size=10"), headers=user)
    assert listed.status_code == 200
    body = listed.json()
    assert body["page"] == 1
    assert body["page_size"] == 10
    assert body["total"] >= 1


def test_reveal_plaintext_admin_only(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user1["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user1,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "u1", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert create_resp.status_code == 201
    created_plaintext = create_resp.json()["api_key_plaintext"]
    key_id = client.get(_api("/api-keys"), headers=user1).json()["items"][0]["id"]

    forbidden = client.post(_api(f"/api-keys/{key_id}/reveal"), headers=user1)
    assert forbidden.status_code == 403

    reveal_resp = client.post(_api(f"/api-keys/{key_id}/reveal"), headers=admin_headers)
    assert reveal_resp.status_code == 200
    assert reveal_resp.json()["api_key_plaintext"] == created_plaintext
    assert reveal_resp.headers["cache-control"] == "no-store"


def test_statistics_allows_query_range_longer_than_31_days(client, admin_headers):
    resp = client.get(
        _api("/api-keys/statistics/users?from=2026-01-01&to=2026-02-15"),
        headers=admin_headers,
    )
    assert resp.status_code == 200


def test_admin_can_update_key_alias_and_user_cannot(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user1["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user1,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "u1", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user1).json()["items"][0]["id"]

    forbidden = client.patch(_api(f"/api-keys/{key_id}"), headers=user1, json={"key_alias": "custom_user_alias"})
    assert forbidden.status_code == 403

    invalid = client.patch(_api(f"/api-keys/{key_id}"), headers=admin_headers, json={"key_alias": "   "})
    assert invalid.status_code == 422

    updated = client.patch(_api(f"/api-keys/{key_id}"), headers=admin_headers, json={"key_alias": "custom_admin_alias"})
    assert updated.status_code == 200
    assert updated.json()["key_alias"] == "custom_admin_alias"

    listed = client.get(_api("/api-keys"), headers=admin_headers)
    assert listed.status_code == 200
    admin_item = next(item for item in listed.json()["items"] if item["id"] == key_id)
    assert admin_item["key_alias"] == "custom_admin_alias"


def test_admin_update_key_alias_syncs_provider_before_local_commit(client, admin_headers, monkeypatch):
    from app.core.config import get_settings

    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user1["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user1,
        json={"application_date": str(date.today()), "duration_days": 180, "purpose": "u1"},
    )
    assert create_resp.status_code == 201
    created_plaintext = create_resp.json()["api_key_plaintext"]
    key_id = client.get(_api("/api-keys"), headers=user1).json()["items"][0]["id"]
    captured_payload: dict = {}

    def _capture_update_payload(self, payload):
        captured_payload.update(payload)
        return SimpleNamespace(request_id=None, operation_id=None)

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    monkeypatch.setenv("PROVIDER_TEAM_ID", "team-001")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)
    monkeypatch.setattr("app.services.provider_client.ProviderClient.update_key", _capture_update_payload)
    try:
        updated = client.patch(_api(f"/api-keys/{key_id}"), headers=admin_headers, json={"key_alias": "custom_admin_alias"})
        assert updated.status_code == 200
        assert updated.json()["key_alias"] == "custom_admin_alias"
        assert captured_payload["key"] == created_plaintext
        assert captured_payload["duration"] == "180d"
        assert captured_payload["key_alias"] == "custom_admin_alias"
        assert captured_payload["team_id"] == "team-001"
        assert captured_payload["key_type"] == "llm_api"
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        monkeypatch.delenv("PROVIDER_TEAM_ID", raising=False)
        get_settings.cache_clear()


def test_admin_update_key_alias_provider_unavailable_leaves_local_alias_unchanged(client, admin_headers, monkeypatch):
    from app.core.config import get_settings
    from app.services.provider_client import ProviderUnavailableError

    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user1["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user1,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "u1"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user1).json()["items"][0]["id"]

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    monkeypatch.setenv("PROVIDER_TEAM_ID", "team-001")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)
    monkeypatch.setattr(
        "app.services.provider_client.ProviderClient.update_key",
        lambda self, payload: (_ for _ in ()).throw(ProviderUnavailableError("provider unavailable")),
    )
    try:
        updated = client.patch(_api(f"/api-keys/{key_id}"), headers=admin_headers, json={"key_alias": "custom_admin_alias"})
        assert updated.status_code == 503
        assert updated.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"

        detail = client.get(_api(f"/api-keys/{key_id}"), headers=admin_headers)
        assert detail.status_code == 200
        assert detail.json()["key_alias"] == "for_user1"
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        monkeypatch.delenv("PROVIDER_TEAM_ID", raising=False)
        get_settings.cache_clear()


def test_admin_update_key_alias_provider_validation_error_leaves_local_alias_unchanged(client, admin_headers, monkeypatch):
    from app.core.config import get_settings
    from app.services.provider_client import ProviderBadRequestError

    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user1["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user1,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "u1"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user1).json()["items"][0]["id"]

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    monkeypatch.setenv("PROVIDER_TEAM_ID", "team-001")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)
    monkeypatch.setattr(
        "app.services.provider_client.ProviderClient.update_key",
        lambda self, payload: (_ for _ in ()).throw(ProviderBadRequestError("body.key_alias: invalid alias")),
    )
    try:
        updated = client.patch(_api(f"/api-keys/{key_id}"), headers=admin_headers, json={"key_alias": "custom_admin_alias"})
        assert updated.status_code == 422
        assert updated.json()["error"]["code"] == "VALIDATION_ERROR"

        detail = client.get(_api(f"/api-keys/{key_id}"), headers=admin_headers)
        assert detail.status_code == 200
        assert detail.json()["key_alias"] == "for_user1"
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        monkeypatch.delenv("PROVIDER_TEAM_ID", raising=False)
        get_settings.cache_clear()


def test_admin_update_key_alias_requires_secret_material_before_provider_call(client, admin_headers, monkeypatch):
    from app.core.config import get_settings

    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user1["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user1,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "u1"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user1).json()["items"][0]["id"]
    _set_key_secret_material(key_id, key_ciphertext=None, key_kek_version=None)

    provider_calls = {"count": 0}

    def _should_not_call_provider(self, payload):
        provider_calls["count"] += 1
        raise AssertionError("provider should not be called without secret material")

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    monkeypatch.setenv("PROVIDER_TEAM_ID", "team-001")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)
    monkeypatch.setattr("app.services.provider_client.ProviderClient.update_key", _should_not_call_provider)
    try:
        updated = client.patch(_api(f"/api-keys/{key_id}"), headers=admin_headers, json={"key_alias": "custom_admin_alias"})
        assert updated.status_code == 409
        assert updated.json()["error"]["code"] == "KEY_NOT_REVEALABLE"
        assert provider_calls["count"] == 0
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        monkeypatch.delenv("PROVIDER_TEAM_ID", raising=False)
        get_settings.cache_clear()


def test_admin_update_key_alias_rejects_duplicates(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    user2 = build_headers(role="user", account="user2", email="user2@example.com", sysid="2002")
    _create_whitelist(client, admin_headers, user1["x-sysid"])
    _create_whitelist(client, admin_headers, user2["x-sysid"])

    for headers in (user1, user2):
        create_resp = client.post(
            _api("/api-keys/applications"),
            headers=headers,
            json={"application_date": str(date.today()), "duration_days": 30, "purpose": headers["x-account"]},
        )
        assert create_resp.status_code == 201

    listed = client.get(_api("/api-keys"), headers=admin_headers)
    assert listed.status_code == 200
    key_by_owner = {item["owner_account"]: item["id"] for item in listed.json()["items"] if item["owner_account"] in {"user1", "user2"}}

    first_update = client.patch(
        _api(f"/api-keys/{key_by_owner['user1']}"),
        headers=admin_headers,
        json={"key_alias": "shared_alias"},
    )
    assert first_update.status_code == 200

    duplicate = client.patch(
        _api(f"/api-keys/{key_by_owner['user2']}"),
        headers=admin_headers,
        json={"key_alias": "shared_alias"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "KEY_ALIAS_DUPLICATE"


def test_admin_update_key_alias_rejects_unsafe_syntax(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user1["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user1,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "u1"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user1).json()["items"][0]["id"]

    invalid = client.patch(_api(f"/api-keys/{key_id}"), headers=admin_headers, json={"key_alias": "foo => bar"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"
    assert invalid.json()["error"]["message"] == "key_alias contains unsafe syntax"


def test_admin_update_key_alias_rejects_invalid_characters(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user1["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user1,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "u1"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user1).json()["items"][0]["id"]

    invalid = client.patch(_api(f"/api-keys/{key_id}"), headers=admin_headers, json={"key_alias": "for_user.1"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"
    assert invalid.json()["error"]["message"] == "key_alias contains invalid characters"


def test_admin_update_key_alias_allows_ideographic_comma(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user1["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user1,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "u1"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user1).json()["items"][0]["id"]

    updated = client.patch(_api(f"/api-keys/{key_id}"), headers=admin_headers, json={"key_alias": "平台、批次_key"})
    assert updated.status_code == 200
    assert updated.json()["key_alias"] == "平台、批次_key"


def test_missing_sysid_rejected_and_no_records_created(client, admin_headers):
    _create_whitelist(client, admin_headers, 8100)
    bad_headers = {
        "x-account": "nosys",
        "x-name": "No Sysid",
        "x-email": "no-sysid@example.com",
        "x-department": "IT",
        "x-role": "user",
    }
    before = client.get(_api("/api-keys"), headers=admin_headers).json()["total"]
    resp = client.post(
        _api("/api-keys/applications"),
        headers=bad_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "test", "max_budget": "1000", "budget_duration": "monthly"},
    )
    after = client.get(_api("/api-keys"), headers=admin_headers).json()["total"]
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert before == after


def test_error_response_shape_consistency(client, admin_headers, user_headers):
    # non-whitelist application error
    e1 = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_days": 30, "purpose": "test", "max_budget": "1000", "budget_duration": "monthly"},
    )
    # non-admin whitelist management error
    e2 = client.get(_api("/whitelists"), headers=user_headers)

    for resp in (e1, e2):
        body = resp.json()
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]
        assert "details" in body["error"]
        assert ":" in body["error"]["details"]


def test_admin_user_statistics_default_sort_scope_and_no_plaintext(client, admin_headers):
    user1 = build_headers(
        role="user", account="alice", email="alice@example.com", sysid=8101, name="Alice", department="R&D"
    )
    user2 = build_headers(
        role="user", account="bob", email="bob@example.com", sysid=8102, name="Bob", department="Security"
    )
    _create_whitelist(client, admin_headers, user1["x-sysid"])
    _create_whitelist(client, admin_headers, user2["x-sysid"])

    for _ in range(2):
        resp = client.post(
            _api("/api-keys/applications"),
            headers=user1,
            json={"application_date": "2026-05-01", "duration_days": 30, "purpose": "u1", "max_budget": "1000", "budget_duration": "monthly"},
        )
        assert resp.status_code == 201
    resp = client.post(
        _api("/api-keys/applications"),
        headers=user2,
        json={"application_date": "2026-05-02", "duration_days": 30, "purpose": "u2", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert resp.status_code == 201

    stats_resp = client.get(_api("/api-keys/statistics/users"), headers=admin_headers)
    assert stats_resp.status_code == 200
    body = stats_resp.json()
    assert body["total"] == 2
    assert body["items"][0]["owner_account"] == "alice"
    assert body["items"][0]["owner_department"] == "R&D"
    assert body["items"][0]["total_applications"] == 2
    assert "api_key_plaintext" not in body["items"][0]


def test_admin_user_statistics_scope_date_range_and_forbidden(client, admin_headers):
    user = build_headers(role="user", account="carol", email="carol@example.com", sysid=8103, name="Carol")
    _create_whitelist(client, admin_headers, user["x-sysid"])

    first = client.post(
        _api("/api-keys/applications"),
        headers=user,
        json={"application_date": "2026-05-01", "duration_days": 30, "purpose": "first", "max_budget": "1000", "budget_duration": "monthly"},
    )
    second = client.post(
        _api("/api-keys/applications"),
        headers=user,
        json={"application_date": "2026-05-03", "duration_days": 30, "purpose": "second", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert first.status_code == 201
    assert second.status_code == 201

    ids = [item["id"] for item in client.get(_api("/api-keys"), headers=user).json()["items"]]
    revoke_target_id = ids[0]
    expire_target_id = ids[1]
    _set_key_expires_at_past(expire_target_id)
    revoke_resp = client.post(_api(f"/api-keys/{revoke_target_id}/revoke"), headers=user)
    assert revoke_resp.status_code == 200

    all_resp = client.get(_api("/api-keys/statistics/users?scope=all"), headers=admin_headers)
    active_resp = client.get(_api("/api-keys/statistics/users?scope=active"), headers=admin_headers)
    revoked_resp = client.get(_api("/api-keys/statistics/users?scope=revoked"), headers=admin_headers)
    expired_resp = client.get(_api("/api-keys/statistics/users?scope=expired"), headers=admin_headers)
    ranged_resp = client.get(
        _api("/api-keys/statistics/users?from=2026-05-02&to=2026-05-03"),
        headers=admin_headers,
    )

    assert all_resp.status_code == 200
    assert active_resp.status_code == 200
    assert revoked_resp.status_code == 200
    assert expired_resp.status_code == 200
    assert ranged_resp.status_code == 200

    all_item = all_resp.json()["items"][0]
    revoked_item = revoked_resp.json()["items"][0]
    ranged_item = ranged_resp.json()["items"][0]

    assert all_item["total_applications"] == 2
    assert active_resp.json()["total"] == 0
    assert revoked_item["total_applications"] == 1
    assert expired_resp.json()["total"] == 1
    assert ranged_item["total_applications"] == 1

    forbidden = client.get(_api("/api-keys/statistics/users"), headers=user)
    assert forbidden.status_code == 403


def test_admin_user_statistics_rejects_invalid_sort_by(client, admin_headers):
    resp = client.get(
        _api("/api-keys/statistics/users?sort_by=__invalid__"),
        headers=admin_headers,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_admin_user_statistics_supports_column_filters(client, admin_headers):
    user1 = build_headers(
        role="user", account="ktu", email="ktu@example.com", sysid=9101, name="KTU", department="IIS"
    )
    user2 = build_headers(
        role="user", account="alice", email="alice@example.com", sysid=9102, name="Alice", department="Security"
    )
    _create_whitelist(client, admin_headers, user1["x-sysid"])
    _create_whitelist(client, admin_headers, user2["x-sysid"])

    for user, application_date in ((user1, "2026-05-01"), (user2, "2026-05-02")):
        resp = client.post(
            _api("/api-keys/applications"),
            headers=user,
            json={
                "application_date": application_date,
                "duration_days": 30,
                "purpose": user["x-account"],
                "max_budget": "1000",
                "budget_duration": "monthly",
            },
        )
        assert resp.status_code == 201

    user1_key_id = client.get(_api("/api-keys"), headers=user1).json()["items"][0]["id"]
    _set_key_owner_snapshot(user1_key_id, name="尤凱婷", department="資訊所")

    filtered = client.get(
        _api(
            "/api-keys/statistics/users?owner_account=kt&owner_name=%E5%B0%A4"
            "&owner_department=%E8%B3%87%E8%A8%8A&sort_by=owner_account&sort_dir=asc"
        ),
        headers=admin_headers,
    )
    assert filtered.status_code == 200
    body = filtered.json()
    assert body["total"] == 1
    assert body["items"][0]["owner_account"] == "ktu"
    assert body["items"][0]["owner_name"] == "尤凱婷"

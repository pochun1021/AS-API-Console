from __future__ import annotations

from datetime import UTC, datetime, timedelta
from contextlib import contextmanager
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import api_path as _api
from tests.db_runtime import begin_connection, get_test_engine


def _create_whitelist(client, admin_headers, sysid: str | int) -> None:
    parsed_sysid = int(sysid)
    resp = client.post(
        _api("/whitelists"),
        headers=admin_headers,
        json={
            "sysid": parsed_sysid,
            "account": f"user{parsed_sysid}",
            "name": f"User {parsed_sysid}",
            "email": f"user{parsed_sysid}@example.com",
            "note": "seed",
        },
    )
    assert resp.status_code == 201


def _db_engine():
    return get_test_engine()


@contextmanager
def _db_begin():
    with begin_connection() as conn:
        yield conn


def _set_key_expires_at_past(key_id: str) -> None:
    past = datetime.now(UTC) - timedelta(days=1)
    with _db_begin() as conn:
        conn.execute(
            text(
                """
                UPDATE api_key_applications a
                JOIN api_keys k ON k.application_id = a.id
                SET a.expires_at = :past
                WHERE k.id = :key_id
                """
            ),
            {"past": past, "key_id": key_id},
        )


def _set_expiration_notice_sent_at(key_id: str, sent_at: datetime | None) -> None:
    with _db_begin() as conn:
        conn.execute(
            text(
                """
                UPDATE api_keys
                SET expiration_notice_sent_at = :sent_at
                WHERE id = :key_id
                """
            ),
            {"sent_at": sent_at, "key_id": key_id},
        )


def _set_key_expires_at_offset_days(key_id: str, *, days: int, hours: int = 1) -> None:
    target_date = (datetime.now(UTC) + timedelta(days=days)).date()
    target = datetime(target_date.year, target_date.month, target_date.day, hours, 0, 0, tzinfo=UTC)
    with _db_begin() as conn:
        conn.execute(
            text(
                """
                UPDATE api_key_applications a
                JOIN api_keys k ON k.application_id = a.id
                SET a.expires_at = :target
                WHERE k.id = :key_id
                """
            ),
            {"target": target, "key_id": key_id},
        )


def _set_key_owner_snapshot(key_id: str, *, name: str | None = None, department: str | None = None) -> None:
    with _db_begin() as conn:
        conn.execute(
            text(
                """
                UPDATE api_key_applications a
                JOIN api_keys k ON k.application_id = a.id
                SET a.name = COALESCE(:name, a.name),
                    a.department = COALESCE(:department, a.department)
                WHERE k.id = :key_id
                """
            ),
            {"name": name, "department": department, "key_id": key_id},
        )


def _set_key_usage_snapshot(
    key_id: str,
    *,
    usage_spend: str | None,
    usage_budget_reset_at: datetime | None,
    usage_synced_at: datetime | None,
    usage_prompt_tokens: int | None = None,
    usage_completion_tokens: int | None = None,
    usage_total_tokens: int | None = None,
) -> None:
    with _db_begin() as conn:
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
                WHERE id = :key_id
                """
            ),
            {
                "usage_spend": usage_spend,
                "usage_prompt_tokens": usage_prompt_tokens,
                "usage_completion_tokens": usage_completion_tokens,
                "usage_total_tokens": usage_total_tokens,
                "usage_budget_reset_at": usage_budget_reset_at,
                "usage_synced_at": usage_synced_at,
                "key_id": key_id,
            },
        )


def _insert_key_usage_snapshot_history(
    key_id: str,
    *,
    spend: str | None,
    budget_reset_at: datetime | None,
    synced_at: datetime,
    bucket_granularity: str | None = None,
    bucket_start_utc: datetime | None = None,
    bucket_end_utc: datetime | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
) -> None:
    with _db_begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO api_key_usage_snapshots (
                    id,
                    api_key_id,
                    bucket_granularity,
                    bucket_start_utc,
                    bucket_end_utc,
                    spend,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    budget_reset_at,
                    synced_at
                )
                VALUES (
                    :id,
                    :api_key_id,
                    :bucket_granularity,
                    :bucket_start_utc,
                    :bucket_end_utc,
                    :spend,
                    :prompt_tokens,
                    :completion_tokens,
                    :total_tokens,
                    :budget_reset_at,
                    :synced_at
                )
                """
            ),
            {
                "id": str(uuid4()),
                "api_key_id": key_id,
                "bucket_granularity": bucket_granularity,
                "bucket_start_utc": bucket_start_utc,
                "bucket_end_utc": bucket_end_utc,
                "spend": spend,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "budget_reset_at": budget_reset_at,
                "synced_at": synced_at,
            },
        )


def _set_application_limits(
    key_id: str,
    *,
    max_budget: str | None = None,
    tpm_limit: int | None = None,
    rpm_limit: int | None = None,
) -> None:
    with _db_begin() as conn:
        conn.execute(
            text(
                """
                UPDATE api_key_applications a
                JOIN api_keys k ON k.application_id = a.id
                SET a.max_budget = COALESCE(:max_budget, a.max_budget),
                    a.tpm_limit = COALESCE(:tpm_limit, a.tpm_limit),
                    a.rpm_limit = COALESCE(:rpm_limit, a.rpm_limit)
                WHERE k.id = :key_id
                """
            ),
            {
                "max_budget": max_budget,
                "tpm_limit": tpm_limit,
                "rpm_limit": rpm_limit,
                "key_id": key_id,
            },
        )


def _set_limit_strategy_config(
    *,
    budget_max_budget: str,
    budget_duration: str,
    rate_limit_tpm: int,
    rate_limit_rpm: int,
    max_parallel_requests: int,
    updated_at: datetime | None = None,
) -> None:
    effective_updated_at = updated_at or datetime.now(UTC)
    with _db_begin() as conn:
        conn.execute(
            text(
                """
                UPDATE limit_strategy_config
                SET budget_max_budget = :budget_max_budget,
                    budget_duration = :budget_duration,
                    rate_limit_tpm = :rate_limit_tpm,
                    rate_limit_rpm = :rate_limit_rpm,
                    max_parallel_requests = :max_parallel_requests,
                    updated_at = COALESCE(:updated_at, updated_at)
                WHERE id = 'global-limit-strategy-config'
                """
            ),
            {
                "budget_max_budget": budget_max_budget,
                "budget_duration": budget_duration,
                "rate_limit_tpm": rate_limit_tpm,
                "rate_limit_rpm": rate_limit_rpm,
                "max_parallel_requests": max_parallel_requests,
                "updated_at": effective_updated_at,
            },
        )


def _fetch_key_row(key_id: str) -> dict:
    with _db_begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT id,
                       created_at,
                       usage_spend,
                       usage_prompt_tokens,
                       usage_completion_tokens,
                       usage_total_tokens,
                       usage_budget_reset_at,
                       usage_synced_at
                FROM api_keys
                WHERE id = :key_id
                """
            ),
            {"key_id": key_id},
        ).mappings().one()
    return dict(row)


def _set_key_secret_material(key_id: str, *, key_ciphertext: str | None, key_kek_version: str | None) -> None:
    with _db_begin() as conn:
        conn.execute(
            text(
                """
                UPDATE api_keys
                SET key_ciphertext = :key_ciphertext,
                    key_kek_version = :key_kek_version
                WHERE id = :key_id
                """
            ),
            {
                "key_ciphertext": key_ciphertext,
                "key_kek_version": key_kek_version,
                "key_id": key_id,
            },
        )


def _fetch_key_status_row(key_id: str) -> dict:
    with _db_begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT k.status AS key_status, a.status AS application_status, a.revoked_at, a.expires_at
                FROM api_keys k
                JOIN api_key_applications a ON a.id = k.application_id
                WHERE k.id = :key_id
                """
            ),
            {"key_id": key_id},
        ).mappings().one()
    return dict(row)


def _fetch_key_notice_state(key_id: str) -> dict:
    with _db_begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT expiration_notice_sent_at
                FROM api_keys
                WHERE id = :key_id
                """
            ),
            {"key_id": key_id},
        ).mappings().one()
    return dict(row)


def _fetch_expiration_notice_rows(key_id: str) -> list[dict]:
    with _db_begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT notice_days_before, status, sent_at, error_message, success_notice_days_before, expires_at_snapshot
                FROM api_key_expiration_notices
                WHERE key_id = :key_id
                ORDER BY created_at ASC, id ASC
                """
            ),
            {"key_id": key_id},
        ).mappings().all()
    return [dict(row) for row in rows]


def _fetch_application_row(application_id: str) -> dict:
    with _db_begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT id, account, name, email, department, sysid, is_proxy_submission, proxy_operator_account
                FROM api_key_applications
                WHERE id = :application_id
                """
            ),
            {"application_id": application_id},
        ).mappings().one()
    return dict(row)


def _fetch_application_row_for_key(key_id: str) -> dict:
    with _db_begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT a.id, a.account, a.name, a.email, a.department, a.sysid, a.is_proxy_submission,
                       a.proxy_operator_account, a.application_date, a.duration_days, a.original_duration_days,
                       a.issued_at, a.expires_at, a.status
                FROM api_key_applications a
                JOIN api_keys k ON k.application_id = a.id
                WHERE k.id = :key_id
                """
            ),
            {"key_id": key_id},
        ).mappings().one()
    return dict(row)


def _assert_utc_datetime_string(value: str) -> None:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    assert value.endswith("Z") or value.endswith("+00:00")

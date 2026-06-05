import json
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from db.models.operation_audit_logs import OperationAuditLog
from tests.conftest import api_path, build_headers


def _query_logs(event_type: str, action: str) -> list[OperationAuditLog]:
    settings = get_settings()
    db_url = settings.test_database_url or settings.database_url
    engine = create_engine(db_url, future=True)
    with Session(engine) as session:
        rows = session.scalars(
            select(OperationAuditLog)
            .where(OperationAuditLog.event_type == event_type, OperationAuditLog.action == action)
            .order_by(OperationAuditLog.created_at.asc())
        ).all()
    return rows


def _delete_limit_strategy_config() -> None:
    settings = get_settings()
    db_url = settings.test_database_url or settings.database_url
    engine = create_engine(db_url, future=True)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM limit_strategy_config WHERE id = 'global-limit-strategy-config'"))


def _count_limit_strategy_config() -> int:
    settings = get_settings()
    db_url = settings.test_database_url or settings.database_url
    engine = create_engine(db_url, future=True)
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT COUNT(*) FROM limit_strategy_config WHERE id = 'global-limit-strategy-config'")
        ).first()
    return int(row[0]) if row is not None else 0


def _create_whitelist(client, admin_headers, sysid: int) -> None:
    resp = client.post(
        api_path("/whitelists"),
        headers=admin_headers,
        json={
            "sysid": sysid,
            "account": f"user{sysid}",
            "name": f"User {sysid}",
            "email": f"user{sysid}@example.com",
            "note": "seed",
        },
    )
    assert resp.status_code == 201


def test_application_create_logs_success_and_failure(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, int(user_headers["x-sysid"]))

    ok = client.post(
        api_path("/api-keys/applications"),
        headers={**user_headers, "x-request-id": "req-app-ok", "x-forwarded-for": "198.51.100.20"},
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "audit"},
    )
    assert ok.status_code == 201

    bad = client.post(
        api_path("/api-keys/applications"),
        headers={**user_headers, "x-request-id": "req-app-fail"},
        json={"application_date": str(date.today()), "duration_months": 2, "purpose": "audit"},
    )
    assert bad.status_code == 422

    logs = _query_logs("api_key_application", "create")
    assert len(logs) == 2
    by_request = {row.request_id: row for row in logs}
    success_row = by_request["req-app-ok"]
    failure_row = by_request["req-app-fail"]

    assert success_row.result == "success"
    assert success_row.source_ip == "198.51.100.20"
    success_meta = json.loads(success_row.metadata_json or "{}")
    assert success_meta["application_id"]
    assert success_meta["duration_months"] == 1
    assert "api_key_plaintext" not in (success_row.metadata_json or "")

    assert failure_row.result == "failure"
    assert failure_row.error_code == "INVALID_DURATION_MONTHS"
    assert failure_row.error_detail == "duration_months must be one of 1, 6, 12"
    failure_meta = json.loads(failure_row.metadata_json or "{}")
    assert failure_meta["duration_months"] == 2


def test_revoke_logs_success_and_failure(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    user2 = build_headers(role="user", account="user2", email="user2@example.com", sysid="2002")
    _create_whitelist(client, admin_headers, 2001)
    create_resp = client.post(
        api_path("/api-keys/applications"),
        headers=user1,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "audit"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(api_path("/api-keys"), headers=user1).json()["items"][0]["id"]

    fail = client.post(api_path(f"/api-keys/{key_id}/revoke"), headers={**user2, "x-request-id": "req-revoke-fail"})
    assert fail.status_code == 403
    ok = client.post(api_path(f"/api-keys/{key_id}/revoke"), headers={**user1, "x-request-id": "req-revoke-ok"})
    assert ok.status_code == 200

    logs = _query_logs("api_key", "revoke")
    assert len(logs) == 2
    by_request = {row.request_id: row for row in logs}
    failure_row = by_request["req-revoke-fail"]
    success_row = by_request["req-revoke-ok"]
    assert failure_row.result == "failure"
    assert failure_row.error_code == "KEY_NOT_OWNED_BY_USER"
    assert failure_row.error_detail == "key is not owned by requester"
    assert failure_row.request_id == "req-revoke-fail"
    assert success_row.result == "success"
    assert success_row.error_detail is None


def test_renew_logs_success_and_failure(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    user2 = build_headers(role="user", account="user2", email="user2@example.com", sysid="2002")
    _create_whitelist(client, admin_headers, 2001)
    create_resp = client.post(
        api_path("/api-keys/applications"),
        headers=user1,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "audit renew"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(api_path("/api-keys"), headers=user1).json()["items"][0]["id"]
    client.post(api_path(f"/api-keys/{key_id}/revoke"), headers=user1)

    fail = client.post(api_path(f"/api-keys/{key_id}/renew"), headers={**user2, "x-request-id": "req-renew-fail"})
    assert fail.status_code == 403
    ok = client.post(api_path(f"/api-keys/{key_id}/renew"), headers={**user1, "x-request-id": "req-renew-ok"})
    assert ok.status_code == 200

    logs = _query_logs("api_key", "renew")
    assert len(logs) == 2
    by_request = {row.request_id: row for row in logs}
    failure_row = by_request["req-renew-fail"]
    success_row = by_request["req-renew-ok"]
    assert failure_row.result == "failure"
    assert failure_row.error_code == "KEY_NOT_OWNED_BY_USER"
    assert failure_row.error_detail == "key is not owned by requester"
    assert success_row.result == "success"


def test_whitelist_create_update_delete_logs_success_and_failure(client, admin_headers, user_headers):
    create_forbidden = client.post(
        api_path("/whitelists"),
        headers=user_headers,
        json={"sysid": 7008, "account": "user7008", "name": "User 7008", "email": "user7008@example.com", "note": "forbidden"},
    )
    assert create_forbidden.status_code == 403
    create_ok = client.post(
        api_path("/whitelists"),
        headers=admin_headers,
        json={"sysid": 7008, "account": "user7008", "name": "User 7008", "email": "user7008@example.com", "note": "ok"},
    )
    assert create_ok.status_code == 201

    whitelist_id = create_ok.json()["id"]
    update_fail = client.patch(
        api_path(f"/whitelists/{whitelist_id}"),
        headers=admin_headers,
        json={"status": "bad-status", "note": "bad"},
    )
    assert update_fail.status_code == 422
    update_ok = client.patch(
        api_path(f"/whitelists/{whitelist_id}"),
        headers=admin_headers,
        json={"status": "inactive", "note": "ok"},
    )
    assert update_ok.status_code == 200
    delete_fail = client.delete(api_path(f"/whitelists/{whitelist_id}"), headers=user_headers)
    assert delete_fail.status_code == 403
    delete_ok = client.delete(api_path(f"/whitelists/{whitelist_id}"), headers=admin_headers)
    assert delete_ok.status_code == 204

    create_logs = _query_logs("whitelist", "create")
    assert len(create_logs) == 2
    assert {row.result for row in create_logs} == {"success", "failure"}
    create_failure_rows = [row for row in create_logs if row.result == "failure"]
    assert len(create_failure_rows) == 1
    assert create_failure_rows[0].error_code == "VALIDATION_ERROR"
    assert create_failure_rows[0].error_detail == "admin role required"

    update_logs = _query_logs("whitelist", "update")
    assert len(update_logs) == 2
    assert {row.result for row in update_logs} == {"success", "failure"}
    failure_rows = [row for row in update_logs if row.result == "failure"]
    assert len(failure_rows) == 1
    assert failure_rows[0].error_code == "VALIDATION_ERROR"
    assert failure_rows[0].error_detail == "status must be active or inactive"

    delete_logs = _query_logs("whitelist", "delete")
    assert len(delete_logs) == 2
    assert {row.result for row in delete_logs} == {"success", "failure"}
    delete_failure_rows = [row for row in delete_logs if row.result == "failure"]
    assert len(delete_failure_rows) == 1
    assert delete_failure_rows[0].error_code == "VALIDATION_ERROR"
    assert delete_failure_rows[0].error_detail == "admin role required"


def test_admin_enable_disable_logs_success_and_failure(client, admin_headers, user_headers):
    fail_enable = client.post(api_path("/admins/999999/enable"), headers=admin_headers)
    assert fail_enable.status_code == 404

    target_admin_headers = build_headers(role="admin", account="u1", email="u1@example.com", sysid=7003)
    bootstrap = client.get(api_path("/api-keys"), headers=target_admin_headers)
    assert bootstrap.status_code == 200

    ok_disable = client.post(api_path("/admins/7003/disable"), headers={**admin_headers, "x-request-id": "req-disable-ok"})
    assert ok_disable.status_code == 200
    forbidden_enable = client.post(api_path("/admins/7003/enable"), headers=user_headers)
    assert forbidden_enable.status_code == 403

    enable_logs = _query_logs("admin_management", "enable")
    assert len(enable_logs) == 2
    assert {row.result for row in enable_logs} == {"failure"}
    assert {row.error_code for row in enable_logs} == {"USER_NOT_FOUND", "VALIDATION_ERROR"}
    assert {row.error_detail for row in enable_logs} == {"admin role required", "admin not found"}


def test_admin_enable_invalid_id_logs_validation_failure(client, admin_headers):
    resp = client.post(api_path("/admins/not-a-number/enable"), headers={**admin_headers, "x-request-id": "req-enable-invalid"})
    assert resp.status_code == 422

    logs = _query_logs("admin_management", "enable")
    target = next(row for row in logs if row.request_id == "req-enable-invalid")
    assert target.error_code == "VALIDATION_ERROR"
    assert target.error_detail == "admin id must be numeric"


def test_unexpected_failure_uses_sanitized_error_detail(client, admin_headers, monkeypatch):
    from app.services.whitelists_service import WhitelistsService

    def boom(self, current_user, sysid, account, name, email, note):  # noqa: ANN001
        raise RuntimeError("db password=secret should not persist")

    monkeypatch.setattr(WhitelistsService, "create", boom)

    with pytest.raises(RuntimeError, match="db password=secret should not persist"):
        client.post(
            api_path("/whitelists"),
            headers={**admin_headers, "x-request-id": "req-whitelist-boom"},
            json={
                "sysid": 7111,
                "account": "user7111",
                "name": "User 7111",
                "email": "user7111@example.com",
                "note": "boom",
            },
        )

    logs = _query_logs("whitelist", "create")
    target = next(row for row in logs if row.request_id == "req-whitelist-boom")
    assert target.error_code == "INTERNAL_ERROR"
    assert target.error_detail == "RuntimeError: unexpected internal failure"
    assert "secret" not in target.error_detail


def test_admin_create_delete_logs_success_and_failure(client, admin_headers):
    create_fail = client.put(
        api_path("/admins/1001"),
        headers={**admin_headers, "x-request-id": "req-admin-create-fail"},
        json={
            "account": "admin",
            "name": "Admin User",
            "email": "admin@example.com",
            "department": "01",
        },
    )
    assert create_fail.status_code == 409

    create_ok = client.put(
        api_path("/admins/5016408"),
        headers={**admin_headers, "x-request-id": "req-admin-create-ok"},
        json={
            "account": "u5016408",
            "name": "User 5016408",
            "email": "u5016408@example.com",
            "department": "01",
        },
    )
    assert create_ok.status_code == 200

    delete_fail = client.delete(api_path("/admins/5016408"), headers={**admin_headers, "x-request-id": "req-admin-delete-fail"})
    assert delete_fail.status_code == 422

    disabled = client.post(api_path("/admins/5016408/disable"), headers=admin_headers)
    assert disabled.status_code == 200
    delete_ok = client.delete(api_path("/admins/5016408"), headers={**admin_headers, "x-request-id": "req-admin-delete-ok"})
    assert delete_ok.status_code == 204

    create_logs = _query_logs("admin_management", "create")
    assert len(create_logs) == 2
    assert {row.result for row in create_logs} == {"success", "failure"}
    assert {row.error_code for row in create_logs if row.result == "failure"} == {"ADMIN_ALREADY_EXISTS"}

    delete_logs = _query_logs("admin_management", "delete")
    assert len(delete_logs) == 2
    by_request = {row.request_id: row for row in delete_logs}
    assert by_request["req-admin-delete-fail"].result == "failure"
    assert by_request["req-admin-delete-fail"].error_code == "VALIDATION_ERROR"
    assert by_request["req-admin-delete-ok"].result == "success"


def test_limit_strategy_config_update_logs_success_and_failure(client, admin_headers, user_headers):
    payload = {
        "budget_max_budget": "2000",
        "budget_duration": "weekly",
        "rate_limit_tpm": 12000,
        "rate_limit_rpm": 600,
    }
    ok = client.patch(
        api_path("/limit-strategy-config"),
        headers={**admin_headers, "x-request-id": "req-limit-ok", "x-forwarded-for": "203.0.113.18"},
        json=payload,
    )
    assert ok.status_code == 200

    forbidden = client.patch(
        api_path("/limit-strategy-config"),
        headers={**user_headers, "x-request-id": "req-limit-forbidden"},
        json=payload,
    )
    assert forbidden.status_code == 403

    fail = client.patch(
        api_path("/limit-strategy-config"),
        headers={**admin_headers, "x-request-id": "req-limit-fail"},
        json={
            "budget_max_budget": "",
            "budget_duration": "monthly",
            "rate_limit_tpm": 10000,
            "rate_limit_rpm": 500,
        },
    )
    assert fail.status_code == 422

    logs = _query_logs("limit_strategy_config", "update")
    assert len(logs) == 2
    by_request = {row.request_id: row for row in logs}
    success_row = by_request["req-limit-ok"]
    forbidden_row = by_request["req-limit-forbidden"]

    assert success_row.result == "success"
    assert success_row.source_ip == "203.0.113.18"
    success_meta = json.loads(success_row.metadata_json or "{}")
    assert success_meta["budget_duration"] == "weekly"
    assert success_meta["rate_limit_tpm"] == 12000
    assert success_meta["rate_limit_rpm"] == 600

    assert forbidden_row.result == "failure"
    assert forbidden_row.error_code == "FORBIDDEN"


def test_limit_strategy_get_returns_defaults_when_row_is_missing(client, admin_headers):
    _delete_limit_strategy_config()
    assert _count_limit_strategy_config() == 0

    resp = client.get(api_path("/limit-strategy-config"), headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json() == {
        "budget_max_budget": "1000",
        "budget_duration": "monthly",
        "rate_limit_tpm": 10000,
        "rate_limit_rpm": 500,
    }
    assert _count_limit_strategy_config() == 0


def test_limit_strategy_patch_upserts_missing_row(client, admin_headers):
    _delete_limit_strategy_config()
    assert _count_limit_strategy_config() == 0

    payload = {
        "budget_max_budget": "3000",
        "budget_duration": "weekly",
        "rate_limit_tpm": 13000,
        "rate_limit_rpm": 700,
    }
    resp = client.patch(api_path("/limit-strategy-config"), headers=admin_headers, json=payload)
    assert resp.status_code == 200
    assert resp.json() == payload
    assert _count_limit_strategy_config() == 1


def test_limit_strategy_patch_accepts_zero_rate_limits(client, admin_headers):
    payload = {
        "budget_max_budget": "3000",
        "budget_duration": "weekly",
        "rate_limit_tpm": 0,
        "rate_limit_rpm": 0,
    }
    resp = client.patch(api_path("/limit-strategy-config"), headers=admin_headers, json=payload)
    assert resp.status_code == 200
    assert resp.json() == payload


def test_user_lookup_logs_success_and_failure(client, admin_headers, monkeypatch):
    target_admin_headers = build_headers(role="admin", account="u1", email="u1@example.com", sysid=7003)
    bootstrap = client.get(api_path("/api-keys"), headers=target_admin_headers)
    assert bootstrap.status_code == 200

    def fake_search_by_keyword(self, keyword, limit=20):
        assert keyword == "u1"
        return [{"sysId": "7003", "cn": "u1", "chName": "User One", "email": "u1@example.com", "instCode": "01", "tCode": "A01"}]

    monkeypatch.setattr(
        "app.services.persnl_soap_service.PersnlSoapService.search_by_keyword",
        fake_search_by_keyword,
    )

    ok = client.get(
        api_path("/users?q=u1&lookup_context=proxy_application"),
        headers={**target_admin_headers, "x-request-id": "req-user-lookup-success", "x-forwarded-for": "198.51.100.44"},
    )
    assert ok.status_code == 200

    bad = client.get(
        api_path("/users?q=u1&lookup_context=wrong"),
        headers={**target_admin_headers, "x-request-id": "req-user-lookup-invalid"},
    )
    assert bad.status_code == 422

    logs = _query_logs("user_lookup", "proxy_application")
    assert len(logs) == 1
    success_row = logs[0]
    assert success_row.result == "success"
    assert success_row.source_ip == "198.51.100.44"
    success_meta = json.loads(success_row.metadata_json or "{}")
    assert success_meta["lookup_context"] == "proxy_application"
    assert success_meta["matched_count"] == 1

    invalid_logs = _query_logs("user_lookup", "wrong")
    assert len(invalid_logs) == 1
    assert invalid_logs[0].result == "failure"
    assert invalid_logs[0].error_code == "VALIDATION_ERROR"


def test_limit_strategy_patch_syncs_provider_team_update(client, admin_headers, monkeypatch):
    payload = {
        "budget_max_budget": "3000",
        "budget_duration": "weekly",
        "rate_limit_tpm": 13000,
        "rate_limit_rpm": 700,
    }
    captured_payload: dict = {}

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    monkeypatch.setenv("PROVIDER_TEAM_ID", "team-001")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)

    def _capture_team_update(self, provider_payload):
        captured_payload.update(provider_payload)
        return SimpleNamespace(request_id="req-team", operation_id="op-team")

    monkeypatch.setattr("app.services.provider_client.ProviderClient.update_team_limits", _capture_team_update)

    try:
        resp = client.patch(api_path("/limit-strategy-config"), headers=admin_headers, json=payload)
        assert resp.status_code == 200
        assert captured_payload == {
            "team_id": "team-001",
            "max_budget": 3000.0,
            "budget_duration": "7d",
            "tpm_limit": 13000,
            "rpm_limit": 700,
        }
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        monkeypatch.delenv("PROVIDER_TEAM_ID", raising=False)
        get_settings.cache_clear()


def test_limit_strategy_patch_requires_team_id_before_provider_call(client, admin_headers, monkeypatch):
    payload = {
        "budget_max_budget": "3000",
        "budget_duration": "weekly",
        "rate_limit_tpm": 13000,
        "rate_limit_rpm": 700,
    }
    _delete_limit_strategy_config()

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    monkeypatch.delenv("PROVIDER_TEAM_ID", raising=False)
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)

    provider_called = {"count": 0}

    def _should_not_call_provider(self, provider_payload):
        provider_called["count"] += 1
        raise AssertionError("provider should not be called when PROVIDER_TEAM_ID is missing")

    monkeypatch.setattr("app.services.provider_client.ProviderClient.update_team_limits", _should_not_call_provider)

    try:
        resp = client.patch(api_path("/limit-strategy-config"), headers=admin_headers, json=payload)
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "PROVIDER_TEAM_ID_REQUIRED"
        assert provider_called["count"] == 0
        assert _count_limit_strategy_config() == 0
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        get_settings.cache_clear()


def test_limit_strategy_patch_rejects_non_ascii_digits_payload(client, admin_headers):
    payload = {
        "budget_max_budget": "１２３",
        "budget_duration": "weekly",
        "rate_limit_tpm": "1e3",
        "rate_limit_rpm": 500,
    }
    resp = client.patch(api_path("/limit-strategy-config"), headers=admin_headers, json=payload)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

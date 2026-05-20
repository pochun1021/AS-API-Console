import json
from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from db.models.operation_audit_logs import OperationAuditLog
from tests.conftest import build_headers


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


def _create_whitelist(client, admin_headers, sysid: int) -> None:
    resp = client.post("/api/v1/whitelists", headers=admin_headers, json={"sysid": sysid, "note": "seed"})
    assert resp.status_code == 201


def test_application_create_logs_success_and_failure(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, int(user_headers["x-sysid"]))

    ok = client.post(
        "/api/v1/api-keys/applications",
        headers={**user_headers, "x-request-id": "req-app-ok", "x-forwarded-for": "198.51.100.20"},
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "audit"},
    )
    assert ok.status_code == 201

    bad = client.post(
        "/api/v1/api-keys/applications",
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
    failure_meta = json.loads(failure_row.metadata_json or "{}")
    assert failure_meta["duration_months"] == 2


def test_revoke_logs_success_and_failure(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    user2 = build_headers(role="user", account="user2", email="user2@example.com", sysid="2002")
    _create_whitelist(client, admin_headers, 2001)
    create_resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user1,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "audit"},
    )
    app_id = create_resp.json()["application"]["id"]
    client.post(f"/api/v1/api-keys/applications/{app_id}/issue", headers=admin_headers)
    key_id = client.get("/api/v1/api-keys", headers=user1).json()["items"][0]["id"]

    fail = client.post(f"/api/v1/api-keys/{key_id}/revoke", headers={**user2, "x-request-id": "req-revoke-fail"})
    assert fail.status_code == 403
    ok = client.post(f"/api/v1/api-keys/{key_id}/revoke", headers={**user1, "x-request-id": "req-revoke-ok"})
    assert ok.status_code == 200

    logs = _query_logs("api_key", "revoke")
    assert len(logs) == 2
    by_request = {row.request_id: row for row in logs}
    failure_row = by_request["req-revoke-fail"]
    success_row = by_request["req-revoke-ok"]
    assert failure_row.result == "failure"
    assert failure_row.error_code == "KEY_NOT_OWNED_BY_USER"
    assert success_row.result == "success"


def test_whitelist_create_and_update_logs_success_and_failure(client, admin_headers, user_headers):
    create_forbidden = client.post(
        "/api/v1/whitelists",
        headers=user_headers,
        json={"sysid": 7008, "note": "forbidden"},
    )
    assert create_forbidden.status_code == 403
    create_ok = client.post("/api/v1/whitelists", headers=admin_headers, json={"sysid": 7008, "note": "ok"})
    assert create_ok.status_code == 201

    whitelist_id = create_ok.json()["id"]
    update_fail = client.patch(
        f"/api/v1/whitelists/{whitelist_id}",
        headers=admin_headers,
        json={"status": "bad-status", "note": "bad"},
    )
    assert update_fail.status_code == 422
    update_ok = client.patch(
        f"/api/v1/whitelists/{whitelist_id}",
        headers=admin_headers,
        json={"status": "inactive", "note": "ok"},
    )
    assert update_ok.status_code == 200

    create_logs = _query_logs("whitelist", "create")
    assert len(create_logs) == 2
    assert {row.result for row in create_logs} == {"success", "failure"}
    create_failure_rows = [row for row in create_logs if row.result == "failure"]
    assert len(create_failure_rows) == 1
    assert create_failure_rows[0].error_code == "VALIDATION_ERROR"

    update_logs = _query_logs("whitelist", "update")
    assert len(update_logs) == 2
    assert {row.result for row in update_logs} == {"success", "failure"}
    failure_rows = [row for row in update_logs if row.result == "failure"]
    assert len(failure_rows) == 1
    assert failure_rows[0].error_code == "VALIDATION_ERROR"


def test_admin_enable_disable_logs_success_and_failure(client, admin_headers, user_headers):
    fail_enable = client.post("/api/v1/admins/not-exist/enable", headers=admin_headers)
    assert fail_enable.status_code == 404

    target_admin_headers = build_headers(role="admin", account="u1", email="u1@example.com", sysid=7003)
    bootstrap = client.get("/api/v1/api-keys", headers=target_admin_headers)
    assert bootstrap.status_code == 200

    ok_disable = client.post("/api/v1/admins/7003/disable", headers={**admin_headers, "x-request-id": "req-disable-ok"})
    assert ok_disable.status_code == 200
    forbidden_enable = client.post("/api/v1/admins/7003/enable", headers=user_headers)
    assert forbidden_enable.status_code == 403

    enable_logs = _query_logs("admin_management", "enable")
    assert len(enable_logs) == 2
    assert {row.result for row in enable_logs} == {"failure"}
    assert {row.error_code for row in enable_logs} == {"USER_NOT_FOUND", "VALIDATION_ERROR"}

    disable_logs = _query_logs("admin_management", "disable")
    assert len(disable_logs) == 1
    assert disable_logs[0].result == "success"
    assert disable_logs[0].request_id == "req-disable-ok"


def test_limit_strategy_config_update_logs_success_and_failure(client, admin_headers, user_headers):
    payload = {
        "budget_max_budget": "2000",
        "budget_duration": "weekly",
        "rate_limit_tpm": 12000,
        "rate_limit_rpm": 600,
    }
    ok = client.patch(
        "/api/v1/limit-strategy-config",
        headers={**admin_headers, "x-request-id": "req-limit-ok", "x-forwarded-for": "203.0.113.18"},
        json=payload,
    )
    assert ok.status_code == 200

    forbidden = client.patch(
        "/api/v1/limit-strategy-config",
        headers={**user_headers, "x-request-id": "req-limit-forbidden"},
        json=payload,
    )
    assert forbidden.status_code == 403

    fail = client.patch(
        "/api/v1/limit-strategy-config",
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
    assert len(logs) == 3
    by_request = {row.request_id: row for row in logs}
    success_row = by_request["req-limit-ok"]
    forbidden_row = by_request["req-limit-forbidden"]
    failure_row = by_request["req-limit-fail"]

    assert success_row.result == "success"
    assert success_row.source_ip == "203.0.113.18"
    success_meta = json.loads(success_row.metadata_json or "{}")
    assert success_meta["budget_duration"] == "weekly"
    assert success_meta["rate_limit_tpm"] == 12000
    assert success_meta["rate_limit_rpm"] == 600

    assert forbidden_row.result == "failure"
    assert forbidden_row.error_code == "FORBIDDEN"

    assert failure_row.result == "failure"
    assert failure_row.error_code == "MISSING_BUDGET_FIELDS"

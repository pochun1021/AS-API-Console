from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from zoneinfo import ZoneInfo

from db.models.auth_audit_logs import AuthAuditLog
from db.models.operation_audit_logs import OperationAuditLog
from tests.conftest import api_path
from tests.db_runtime import session_scope


TAIPEI_TZ = ZoneInfo("Asia/Taipei")


def _insert_auth_log(created_at: datetime, provider: str, result: str) -> None:
    with session_scope() as session:
        row = AuthAuditLog(
            id=str(uuid4()),
            provider=provider,
            request_id=f"req-{uuid4()}",
            result=result,
            error_code=None if result == "success" else "OAUTH_CODE_MISSING",
            account="oauth.user",
            name="OAuth User",
            email="oauth.user@example.com",
            department="IT",
            sysid=3001,
            role="user",
            detail=None,
            created_at=created_at,
        )
        session.add(row)
        session.commit()


def _insert_operation_log(created_at: datetime, event_type: str, result: str) -> None:
    with session_scope() as session:
        request_id = f"req-{uuid4()}"
        row = OperationAuditLog(
            id=str(uuid4()),
            event_type=event_type,
            action="test",
            result=result,
            error_code=None if result == "success" else "TEST_FAIL",
            error_detail=None if result == "success" else "validation failed for test payload",
            actor_sysid=1001,
            actor_account="admin",
            actor_role="admin",
            target_type="test_target",
            target_id="t1",
            request_id=request_id,
            source_ip="127.0.0.1",
            user_agent="pytest",
            metadata_json=None,
            created_at=created_at,
        )
        session.add(row)
        session.commit()


def _assert_utc_string(value: str) -> None:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    assert value.endswith("Z") or value.endswith("+00:00")


def _write_scheduler_log(log_root: Path, job: str, log_date: str, lines: list[str]) -> None:
    log_dir = log_root / job
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / f"{log_date}.log").write_text("\n".join(lines) + "\n", encoding="utf-8")


test_cases = [
    {
        "name": "auth audit logs",
        "path": "/auth-audit-logs",
        "insert_logs": lambda now: (
            _insert_auth_log(now - timedelta(days=2), "test-oauth", "success"),
            _insert_auth_log(now - timedelta(days=10), "test-oauth", "failure"),
            _insert_auth_log(now - timedelta(days=1), "other-oauth", "failure"),
        ),
        "item_field": "provider",
        "expected_values": {"test-oauth", "other-oauth"},
        "filter_query": "/auth-audit-logs?provider=other-oauth&result=failure",
        "filter_field": "provider",
        "filter_value": "other-oauth",
    },
    {
        "name": "operation audit logs",
        "path": "/operation-audit-logs",
        "insert_logs": lambda now: (
            _insert_operation_log(now - timedelta(days=2), "api_key", "success"),
            _insert_operation_log(now - timedelta(days=10), "api_key", "failure"),
            _insert_operation_log(now - timedelta(days=1), "whitelist", "failure"),
        ),
        "item_field": "event_type",
        "expected_values": {"api_key", "whitelist"},
        "filter_query": "/operation-audit-logs?event_type=whitelist&result=failure",
        "filter_field": "event_type",
        "filter_value": "whitelist",
    },
]


def test_audit_logs_admin_only(client, admin_headers, user_headers):
    for case in test_cases:
      denied = client.get(api_path(case["path"]), headers=user_headers)
      assert denied.status_code == 403

      ok = client.get(api_path(case["path"]), headers=admin_headers)
      assert ok.status_code == 200


def test_audit_logs_default_hot_window_and_filters(client, admin_headers):
    for case in test_cases:
        now = datetime.now(UTC)
        case["insert_logs"](now)

        resp = client.get(api_path(case["path"]), headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 2
        assert all(item[case["item_field"]] in case["expected_values"] for item in body["items"])
        _assert_utc_string(body["items"][0]["created_at"])

        filtered = client.get(api_path(case["filter_query"]), headers=admin_headers)
        assert filtered.status_code == 200
        filtered_body = filtered.json()
        assert filtered_body["total"] == 1
        assert filtered_body["items"][0][case["filter_field"]] == case["filter_value"]
        assert filtered_body["items"][0]["result"] == "failure"
        if case["name"] == "operation audit logs":
            assert filtered_body["items"][0]["request_id"].startswith("req-")
            assert filtered_body["items"][0]["error_detail"] == "validation failed for test payload"


def test_operation_audit_logs_support_full_server_side_query_contract(client, admin_headers):
    now = datetime.now(UTC)
    _insert_operation_log(now - timedelta(days=2), "api_key", "success")
    _insert_operation_log(now - timedelta(days=1), "whitelist", "failure")

    with session_scope() as session:
        rows = session.query(OperationAuditLog).order_by(OperationAuditLog.created_at.asc()).all()
        rows[0].action = "create"
        rows[0].actor_account = "alice.admin"
        rows[0].target_type = "api_key"
        rows[0].target_id = "key-alpha"
        rows[0].error_code = "OK"
        rows[1].action = "disable"
        rows[1].actor_account = "john.admin"
        rows[1].target_type = "whitelist"
        rows[1].target_id = "wl-beta"
        rows[1].error_code = "VALIDATION_ERROR"
        session.commit()

    resp = client.get(
        api_path(
            "/operation-audit-logs?event_type=whitelist&action=able&result=failure"
            "&actor_account=john&target_type=whitelist&target_id=beta&error_code=VALIDATION"
            "&sort_by=actor_account&sort_dir=asc"
        ),
        headers=admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["actor_account"] == "john.admin"
    assert body["items"][0]["action"] == "disable"
    assert body["items"][0]["target_id"] == "wl-beta"


def test_auth_audit_logs_support_full_server_side_query_contract(client, admin_headers):
    now = datetime.now(UTC)
    _insert_auth_log(now - timedelta(days=2), "sso", "success")
    _insert_auth_log(now - timedelta(days=1), "sso", "failure")

    with session_scope() as session:
        rows = session.query(AuthAuditLog).order_by(AuthAuditLog.created_at.asc()).all()
        rows[0].account = "alice.user"
        rows[0].sysid = 501
        rows[0].role = "user"
        rows[0].error_code = "AUTH_OK"
        rows[0].request_id = "req-auth-alpha"
        rows[1].account = "john.admin"
        rows[1].sysid = 1001
        rows[1].role = "admin"
        rows[1].error_code = "LOGIN_NOT_ELIGIBLE"
        rows[1].request_id = "req-auth-beta"
        session.commit()

    resp = client.get(
        api_path(
            "/auth-audit-logs?provider=sso&result=failure&account=john&sysid=1001&role=admin"
            "&error_code=ELIGIBLE&request_id=beta&sort_by=request_id&sort_dir=desc"
        ),
        headers=admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["account"] == "john.admin"
    assert body["items"][0]["sysid"] == 1001
    assert body["items"][0]["request_id"] == "req-auth-beta"


def test_audit_logs_reject_invalid_sort_fields(client, admin_headers):
    operation = client.get(api_path("/operation-audit-logs?sort_by=__invalid__"), headers=admin_headers)
    assert operation.status_code == 422
    assert operation.json()["error"]["message"] == "sort_by is invalid"

    auth = client.get(api_path("/auth-audit-logs?sort_dir=sideways"), headers=admin_headers)
    assert auth.status_code == 422
    assert auth.json()["error"]["message"] == "sort_dir must be asc or desc"


def test_scheduler_logs_admin_only(client, admin_headers, user_headers, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.scheduler_log_query_service.get_settings", lambda: type("S", (), {"scheduler_log_root": str(tmp_path)})())
    _write_scheduler_log(
        tmp_path,
        "sync_expired_api_keys",
        "2026-06-17",
        ["[2026-06-17T00:05:01+08:00] level=INFO event=expired_key_sync updated_count=3 status=success"],
    )

    denied = client.get(api_path("/scheduler-logs"), headers=user_headers)
    assert denied.status_code == 403

    ok = client.get(api_path("/scheduler-logs"), headers=admin_headers)
    assert ok.status_code == 200
    body = ok.json()
    assert body["available_files"] == []
    assert body["total"] == 1
    assert body["items"][0]["job"] == "sync_expired_api_keys"


def test_scheduler_logs_support_default_window_filters_sort_and_pagination(client, admin_headers, tmp_path, monkeypatch):
    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            frozen = datetime(2026, 6, 17, 9, 30, tzinfo=TAIPEI_TZ)
            return frozen if tz is None else frozen.astimezone(tz)

    monkeypatch.setattr("app.services.scheduler_log_query_service.get_settings", lambda: type("S", (), {"scheduler_log_root": str(tmp_path)})())
    monkeypatch.setattr("app.services.scheduler_log_query_service.datetime", _FrozenDateTime)
    _write_scheduler_log(
        tmp_path,
        "sync_api_key_usage",
        "2026-06-17",
        [
            "[2026-06-17T00:05:01+08:00] level=INFO event=usage_sync mode=sync processed_keys=10 success=9 failed=1",
            "[2026-06-17T00:15:01+08:00] level=ERROR event=usage_sync mode=sync processed_keys=10 success=8 failed=2",
        ],
    )
    _write_scheduler_log(
        tmp_path,
        "send_expiration_reminders",
        "2026-06-16",
        ["[2026-06-16T08:00:00+08:00] level=WARNING event=expiration_notice sent=0 failed=1"],
    )
    _write_scheduler_log(
        tmp_path,
        "sync_expired_api_keys",
        "2026-06-10",
        ["[2026-06-10T00:05:01+08:00] level=INFO event=expired_key_sync updated_count=3 status=success"],
    )

    resp = client.get(api_path("/scheduler-logs"), headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["available_files"] == []
    assert body["total"] == 3
    assert [item["job"] for item in body["items"]] == [
        "sync_api_key_usage",
        "sync_api_key_usage",
        "send_expiration_reminders",
    ]
    assert body["items"][0]["source_file"] == "2026-06-17.log"
    assert body["items"][0]["timestamp"] == "2026-06-17T00:15:01+08:00"
    assert body["items"][0]["raw_line"].startswith("[2026-06-17T00:15:01+08:00] level=ERROR")

    filtered = client.get(
        api_path("/scheduler-logs?job=sync_api_key_usage&level=ERROR&q=failed=2"),
        headers=admin_headers,
    )
    assert filtered.status_code == 200
    filtered_body = filtered.json()
    assert filtered_body["available_files"] == [{"log_date": "2026-06-17", "source_file": "2026-06-17.log"}]
    assert filtered_body["total"] == 1
    assert filtered_body["items"][0]["level"] == "ERROR"
    assert filtered_body["items"][0]["message"] == "event=usage_sync mode=sync processed_keys=10 success=8 failed=2"

    asc = client.get(api_path("/scheduler-logs?sort_dir=asc&page=1&page_size=2"), headers=admin_headers)
    assert asc.status_code == 200
    asc_body = asc.json()
    assert asc_body["total"] == 3
    assert len(asc_body["items"]) == 2
    assert asc_body["items"][0]["timestamp"] == "2026-06-16T08:00:00+08:00"
    assert asc_body["items"][1]["timestamp"] == "2026-06-17T00:05:01+08:00"

    missing = client.get(
        api_path("/scheduler-logs?job=sync_expired_api_keys&from=2026-06-15&to=2026-06-15"),
        headers=admin_headers,
    )
    assert missing.status_code == 200
    assert missing.json()["total"] == 0

    latest = client.get(api_path("/scheduler-logs?file_mode=latest"), headers=admin_headers)
    assert latest.status_code == 200
    latest_body = latest.json()
    assert latest_body["total"] == 4
    assert {item["source_file"] for item in latest_body["items"]} == {"2026-06-17.log", "2026-06-16.log", "2026-06-10.log"}

    all_logs = client.get(api_path("/scheduler-logs?job=sync_api_key_usage&file_mode=all"), headers=admin_headers)
    assert all_logs.status_code == 200
    all_body = all_logs.json()
    assert all_body["total"] == 2
    assert {item["source_file"] for item in all_body["items"]} == {"2026-06-17.log"}


def test_scheduler_logs_reject_invalid_query_params(client, admin_headers, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.scheduler_log_query_service.get_settings", lambda: type("S", (), {"scheduler_log_root": str(tmp_path)})())

    invalid_job = client.get(api_path("/scheduler-logs?job=bad-job"), headers=admin_headers)
    assert invalid_job.status_code == 422
    assert invalid_job.json()["error"]["message"] == "job is invalid"

    invalid_level = client.get(api_path("/scheduler-logs?level=DEBUG"), headers=admin_headers)
    assert invalid_level.status_code == 422
    assert invalid_level.json()["error"]["message"] == "level is invalid"

    invalid_file_mode = client.get(api_path("/scheduler-logs?file_mode=recent"), headers=admin_headers)
    assert invalid_file_mode.status_code == 422
    assert invalid_file_mode.json()["error"]["message"] == "file_mode is invalid"

    invalid_sort_dir = client.get(api_path("/scheduler-logs?sort_dir=sideways"), headers=admin_headers)
    assert invalid_sort_dir.status_code == 422
    assert invalid_sort_dir.json()["error"]["message"] == "sort_dir must be asc or desc"

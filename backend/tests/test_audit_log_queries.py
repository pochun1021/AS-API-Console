from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
from db.models.auth_audit_logs import AuthAuditLog
from db.models.operation_audit_logs import OperationAuditLog
from tests.conftest import api_path


def _engine():
    settings = get_settings()
    db_url = settings.test_database_url or settings.database_url
    return create_engine(db_url, future=True)


def _insert_auth_log(created_at: datetime, provider: str, result: str) -> None:
    with Session(_engine()) as session:
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
    with Session(_engine()) as session:
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
        assert body["total"] == 2
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

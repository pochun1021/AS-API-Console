from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
from db.models.auth_audit_logs import AuthAuditLog
from tests.conftest import api_path


def _insert_log(created_at: datetime, provider: str, result: str) -> None:
    settings = get_settings()
    db_url = settings.test_database_url or settings.database_url
    engine = create_engine(db_url, future=True)
    with Session(engine) as session:
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


def test_auth_audit_logs_admin_only(client, admin_headers, user_headers):
    denied = client.get(api_path("/auth-audit-logs"), headers=user_headers)
    assert denied.status_code == 403

    ok = client.get(api_path("/auth-audit-logs"), headers=admin_headers)
    assert ok.status_code == 200


def test_auth_audit_logs_default_hot_window_and_filters(client, admin_headers):
    now = datetime.now(UTC)
    _insert_log(now - timedelta(days=2), "test-oauth", "success")
    _insert_log(now - timedelta(days=10), "test-oauth", "failure")
    _insert_log(now - timedelta(days=1), "other-oauth", "failure")

    resp = client.get(api_path("/auth-audit-logs"), headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert all(item["provider"] in {"test-oauth", "other-oauth"} for item in body["items"])
    created_at = body["items"][0]["created_at"]
    parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    assert created_at.endswith("Z") or created_at.endswith("+00:00")

    filtered = client.get(
        api_path("/auth-audit-logs?provider=other-oauth&result=failure"),
        headers=admin_headers,
    )
    assert filtered.status_code == 200
    filtered_body = filtered.json()
    assert filtered_body["total"] == 1
    assert filtered_body["items"][0]["provider"] == "other-oauth"
    assert filtered_body["items"][0]["result"] == "failure"

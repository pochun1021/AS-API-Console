import json
from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import inspect
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from db.models.notifications import Notification
from tests.test_api_keys import _create_whitelist


def _issue_and_get_application_id(client, admin_headers, user_headers) -> str:
    _create_whitelist(client, admin_headers, user_headers["x-email"])
    create_resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "notifications"},
    )
    assert create_resp.status_code == 201
    app_id = create_resp.json()["application"]["id"]
    mode_resp = client.patch(
        f"/api/v1/api-keys/applications/{app_id}/issuance-mode",
        headers=admin_headers,
        json={"mode": "budget"},
    )
    assert mode_resp.status_code == 200
    issue_resp = client.post(f"/api/v1/api-keys/applications/{app_id}/issue", headers=admin_headers)
    assert issue_resp.status_code == 200
    return app_id


def test_notifications_list_only_current_sysid(client, admin_headers):
    user1 = {
        "x-account": "user1",
        "x-name": "User One",
        "x-email": "user1@example.com",
        "x-department": "IT",
        "x-sysid": "user-1",
        "x-role": "user",
    }
    user2 = {
        "x-account": "user2",
        "x-name": "User Two",
        "x-email": "user2@example.com",
        "x-department": "IT",
        "x-sysid": "user-2",
        "x-role": "user",
    }

    app1 = _issue_and_get_application_id(client, admin_headers, user1)
    _issue_and_get_application_id(client, admin_headers, user2)

    list_user1 = client.get("/api/v1/notifications", headers=user1)
    assert list_user1.status_code == 200
    body = list_user1.json()
    assert body["total"] == 1
    assert body["items"][0]["metadata"]["application_id"] == app1

    list_user2 = client.get("/api/v1/notifications", headers=user2)
    assert list_user2.status_code == 200
    assert list_user2.json()["total"] == 1


def test_mark_notification_read_and_cross_sysid_forbidden(client, admin_headers):
    user1 = {
        "x-account": "user1",
        "x-name": "User One",
        "x-email": "user1@example.com",
        "x-department": "IT",
        "x-sysid": "user-1",
        "x-role": "user",
    }
    user2 = {
        "x-account": "user2",
        "x-name": "User Two",
        "x-email": "user2@example.com",
        "x-department": "IT",
        "x-sysid": "user-2",
        "x-role": "user",
    }

    _issue_and_get_application_id(client, admin_headers, user1)
    item = client.get("/api/v1/notifications", headers=user1).json()["items"][0]

    forbidden = client.patch(f"/api/v1/notifications/{item['id']}/read", headers=user2)
    assert forbidden.status_code == 404

    marked = client.patch(f"/api/v1/notifications/{item['id']}/read", headers=user1)
    assert marked.status_code == 200
    assert marked.json()["is_read"] is True
    assert marked.json()["read_at"] is not None
    assert marked.json()["revealed"] is True
    assert marked.json()["api_key_plaintext"].startswith("AS-")

    marked_again = client.patch(f"/api/v1/notifications/{item['id']}/read", headers=user1)
    assert marked_again.status_code == 200
    assert marked_again.json()["is_read"] is True
    assert marked_again.json()["revealed"] is False
    assert marked_again.json()["api_key_plaintext"] is None


def test_admin_cannot_mark_other_user_notification_read(client, admin_headers):
    user1 = {
        "x-account": "user1",
        "x-name": "User One",
        "x-email": "user1@example.com",
        "x-department": "IT",
        "x-sysid": "user-1",
        "x-role": "user",
    }
    _issue_and_get_application_id(client, admin_headers, user1)
    item = client.get("/api/v1/notifications", headers=user1).json()["items"][0]

    outsider_admin = {
        "x-account": "another.admin",
        "x-name": "Another Admin",
        "x-email": "another.admin@example.com",
        "x-department": "IT",
        "x-sysid": "admin-2",
        "x-role": "admin",
    }
    forbidden = client.patch(f"/api/v1/notifications/{item['id']}/read", headers=outsider_admin)
    assert forbidden.status_code == 404


def test_mark_notification_read_reveals_plaintext_with_legacy_application_id_only(client, admin_headers):
    user1 = {
        "x-account": "user1",
        "x-name": "User One",
        "x-email": "user1@example.com",
        "x-department": "IT",
        "x-sysid": "user-1",
        "x-role": "user",
    }
    app_id = _issue_and_get_application_id(client, admin_headers, user1)

    existing = client.get("/api/v1/notifications", headers=user1).json()["items"][0]
    legacy_id = str(uuid4())
    settings = get_settings()
    engine = create_engine(settings.test_database_url or settings.database_url, future=True)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    with TestingSessionLocal() as db:
        db.add(
            Notification(
                id=legacy_id,
                sysid=user1["x-sysid"],
                type="api_key_issued",
                title="legacy",
                message="legacy",
                is_read=False,
                metadata_json=json.dumps({"application_id": app_id}, ensure_ascii=False),
                email_delivery_status=None,
                email_error=None,
                created_at=datetime.now(UTC),
                read_at=None,
            )
        )
        db.query(Notification).filter(Notification.id == existing["id"]).delete()
        db.commit()

    marked = client.patch(f"/api/v1/notifications/{legacy_id}/read", headers=user1)
    assert marked.status_code == 200
    assert marked.json()["revealed"] is True
    assert marked.json()["api_key_plaintext"].startswith("AS-")


def test_notification_model_uses_sysid_column_only():
    columns = {col.name for col in inspect(Notification).columns}
    assert "sysid" in columns
    assert "user_id" not in columns

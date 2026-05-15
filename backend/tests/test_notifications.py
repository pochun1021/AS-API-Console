from datetime import date

from tests.conftest import build_headers


def _create_whitelist(client, admin_headers, email: str) -> None:
    resp = client.post("/api/v1/whitelists", headers=admin_headers, json={"email": email, "note": "seed"})
    assert resp.status_code == 201


def _issue_one_application(client, admin_headers, user_headers) -> str:
    create_resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "notify test"},
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
    assert issue_resp.json()["issuance_status"] == "issued"
    return app_id


def test_issue_creates_notification_and_user_can_read_mark(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-email"])
    app_id = _issue_one_application(client, admin_headers, user_headers)

    list_resp = client.get("/api/v1/notifications", headers=user_headers)
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert body["total"] >= 1
    item = body["items"][0]
    assert item["type"] == "api_key_issued"
    assert item["metadata"]["application_id"] == app_id
    assert item["is_read"] is False

    read_resp = client.patch(f"/api/v1/notifications/{item['id']}/read", headers=user_headers)
    assert read_resp.status_code == 200
    assert read_resp.json()["is_read"] is True


def test_notifications_are_owner_scoped(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="user-1")
    user2 = build_headers(role="user", account="user2", email="user2@example.com", sysid="user-2")
    _create_whitelist(client, admin_headers, user1["x-email"])
    _create_whitelist(client, admin_headers, user2["x-email"])

    _issue_one_application(client, admin_headers, user1)

    user1_list = client.get("/api/v1/notifications", headers=user1)
    assert user1_list.status_code == 200
    note_id = user1_list.json()["items"][0]["id"]

    forbidden = client.patch(f"/api/v1/notifications/{note_id}/read", headers=user2)
    assert forbidden.status_code == 404

    user2_list = client.get("/api/v1/notifications", headers=user2)
    assert user2_list.status_code == 200
    assert user2_list.json()["total"] == 0

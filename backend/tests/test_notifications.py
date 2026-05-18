from tests.conftest import build_headers


def test_notifications_list_disabled(client, user_headers):
    resp = client.get("/api/v1/notifications", headers=user_headers)
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "FEATURE_DISABLED"


def test_notifications_mark_read_disabled(client):
    user = build_headers(role="user", account="user1", email="user1@example.com", sysid="user-1")
    resp = client.patch("/api/v1/notifications/any/read", headers=user)
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "FEATURE_DISABLED"


def test_notifications_mark_all_disabled(client):
    user = build_headers(role="user", account="user1", email="user1@example.com", sysid="user-1")
    resp = client.patch("/api/v1/notifications/read-all", headers=user)
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "FEATURE_DISABLED"

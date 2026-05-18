
from tests.conftest import build_headers


def test_whitelist_admin_only(client, admin_headers, user_headers):
    user_resp = client.get("/api/v1/whitelists", headers=user_headers)
    assert user_resp.status_code == 403

    admin_resp = client.post(
        "/api/v1/whitelists",
        headers=admin_headers,
        json={"email": "wl1@example.com", "note": "seed"},
    )
    assert admin_resp.status_code == 201


def test_whitelist_duplicate_email(client, admin_headers):
    payload = {"email": "dup@example.com", "note": "seed"}
    first = client.post("/api/v1/whitelists", headers=admin_headers, json=payload)
    second = client.post("/api/v1/whitelists", headers=admin_headers, json=payload)
    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "WHITELIST_EMAIL_DUPLICATED"


def test_users_admin_role_endpoints(client, admin_headers):
    # bootstrap another admin identity via auth headers
    target_admin_headers = build_headers(role="admin", account="u1", email="u1@example.com", sysid="u1-sys")
    bootstrap = client.get("/api/v1/api-keys", headers=target_admin_headers)
    assert bootstrap.status_code == 200

    users = client.get("/api/v1/users?q=u1", headers=admin_headers)
    assert users.status_code == 200
    assert users.json()["total"] >= 1
    user_item = users.json()["items"][0]
    user_id = user_item["id"]
    assert "sysid" in user_item
    assert user_item["sysid"] == user_item["id"]

    enable = client.post(f"/api/v1/admins/{user_id}/enable", headers=admin_headers)
    assert enable.status_code == 200
    assert enable.json()["role"] == "admin"
    assert enable.json()["status"] == "active"

    disable = client.post(f"/api/v1/admins/{user_id}/disable", headers=admin_headers)
    assert disable.status_code == 200
    assert disable.json()["role"] == "admin"
    assert disable.json()["status"] == "inactive"

    disabled_list = client.get("/api/v1/api-keys", headers=target_admin_headers)
    assert disabled_list.status_code == 403
    assert disabled_list.json()["error"]["code"] == "FORBIDDEN"


def test_user_not_found_for_role_mutation(client, admin_headers):
    resp = client.post("/api/v1/admins/not-exist/enable", headers=admin_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "USER_NOT_FOUND"

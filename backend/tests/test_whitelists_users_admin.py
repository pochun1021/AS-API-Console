
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
    # seed user via application flow
    client.post("/api/v1/whitelists", headers=admin_headers, json={"email": "u1@example.com", "note": "seed"})
    user_headers = build_headers(role="user", account="u1", email="u1@example.com", sysid="u1-sys")
    app_resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user_headers,
        json={"application_date": "2026-05-06", "duration_months": 1, "purpose": "seed"},
    )
    assert app_resp.status_code == 201

    users = client.get("/api/v1/users?q=u1", headers=admin_headers)
    assert users.status_code == 200
    assert users.json()["total"] >= 1
    user_item = users.json()["items"][0]
    user_id = user_item["id"]
    assert "sysid" in user_item
    assert user_item["sysid"] == user_item["id"]

    grant = client.post(f"/api/v1/users/{user_id}/grant-admin", headers=admin_headers)
    assert grant.status_code == 200
    assert grant.json()["role"] == "admin"

    revoke = client.post(f"/api/v1/users/{user_id}/revoke-admin", headers=admin_headers)
    assert revoke.status_code == 200
    assert revoke.json()["role"] == "user"


def test_user_not_found_for_role_mutation(client, admin_headers):
    resp = client.post("/api/v1/users/not-exist/grant-admin", headers=admin_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "USER_NOT_FOUND"

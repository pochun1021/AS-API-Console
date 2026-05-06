from datetime import date

from tests.conftest import build_headers


def _create_whitelist(client, admin_headers, email: str) -> None:
    resp = client.post("/api/v1/whitelists", headers=admin_headers, json={"email": email, "note": "seed"})
    assert resp.status_code == 201


def test_application_success_and_no_plaintext_in_queries(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-email"])

    create_resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test"},
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["api_key_plaintext"].startswith("AS-")
    assert len(body["api_key_plaintext"]) == 33

    list_resp = client.get("/api/v1/api-keys", headers=user_headers)
    assert list_resp.status_code == 200
    item = list_resp.json()["items"][0]
    assert "api_key_plaintext" not in item
    key_id = item["id"]

    detail_resp = client.get(f"/api/v1/api-keys/{key_id}", headers=user_headers)
    assert detail_resp.status_code == 200
    assert "api_key_plaintext" not in detail_resp.json()


def test_application_rejects_non_whitelisted(client, user_headers):
    resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "APPLICANT_NOT_WHITELISTED"


def test_application_rejects_invalid_duration(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-email"])
    resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_months": 2, "purpose": "test"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_DURATION_MONTHS"


def test_application_rejects_future_date(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-email"])
    resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user_headers,
        json={"application_date": "2999-01-01", "duration_months": 1, "purpose": "test"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_APPLICATION_DATE"


def test_revoke_permissions_and_status_checks(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="user-1")
    user2 = build_headers(role="user", account="user2", email="user2@example.com", sysid="user-2")

    _create_whitelist(client, admin_headers, user1["x-email"])

    create_resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user1,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test"},
    )
    key_id = client.get("/api/v1/api-keys", headers=user1).json()["items"][0]["id"]
    assert create_resp.status_code == 201

    not_owner = client.post(f"/api/v1/api-keys/{key_id}/revoke", headers=user2)
    assert not_owner.status_code == 403
    assert not_owner.json()["error"]["code"] == "KEY_NOT_OWNED_BY_USER"

    first = client.post(f"/api/v1/api-keys/{key_id}/revoke", headers=user1)
    assert first.status_code == 200
    assert first.json()["status"] == "revoked"

    second = client.post(f"/api/v1/api-keys/{key_id}/revoke", headers=user1)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "KEY_NOT_ACTIVE"

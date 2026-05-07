from datetime import date

from app.services.research_eligibility_service import ResearchEligibilityResult
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
    assert "application_date" in item
    assert "duration_months" in item
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
    assert resp.json()["error"]["code"] == "APPLICANT_NOT_ELIGIBLE"


def test_application_success_for_research_eligible_without_whitelist(client, user_headers, monkeypatch):
    monkeypatch.setattr(
        "app.services.api_keys_service.ResearchEligibilityService.is_configured",
        lambda self: True,
    )
    monkeypatch.setattr(
        "app.services.api_keys_service.ResearchEligibilityService.check_eligibility",
        lambda self, email, sysid: ResearchEligibilityResult(eligible=True, title_code="RS01"),
    )

    create_resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test"},
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["api_key_plaintext"].startswith("AS-")


def test_application_research_service_unavailable_returns_503_and_no_records(client, admin_headers, user_headers, monkeypatch):
    _create_whitelist(client, admin_headers, user_headers["x-email"])
    monkeypatch.setattr(
        "app.services.api_keys_service.ResearchEligibilityService.is_configured",
        lambda self: True,
    )

    def _raise_unavailable(self, email, sysid):
        raise RuntimeError("timeout")

    monkeypatch.setattr(
        "app.services.api_keys_service.ResearchEligibilityService.check_eligibility",
        _raise_unavailable,
    )

    before = client.get("/api/v1/api-keys", headers=admin_headers).json()["total"]
    resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test"},
    )
    after = client.get("/api/v1/api-keys", headers=admin_headers).json()["total"]

    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "RESEARCH_LIST_SERVICE_UNAVAILABLE"
    assert before == after


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


def test_admin_can_list_global_keys(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="user-1")
    user2 = build_headers(role="user", account="user2", email="user2@example.com", sysid="user-2")
    _create_whitelist(client, admin_headers, user1["x-email"])
    _create_whitelist(client, admin_headers, user2["x-email"])

    resp1 = client.post(
        "/api/v1/api-keys/applications",
        headers=user1,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "u1"},
    )
    resp2 = client.post(
        "/api/v1/api-keys/applications",
        headers=user2,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "u2"},
    )
    assert resp1.status_code == 201
    assert resp2.status_code == 201

    admin_list = client.get("/api/v1/api-keys", headers=admin_headers)
    assert admin_list.status_code == 200
    owners = {item["owner_account"] for item in admin_list.json()["items"]}
    assert "user1" in owners
    assert "user2" in owners


def test_missing_sysid_rejected_and_no_records_created(client, admin_headers):
    _create_whitelist(client, admin_headers, "no-sysid@example.com")
    bad_headers = {
        "x-account": "nosys",
        "x-name": "No Sysid",
        "x-email": "no-sysid@example.com",
        "x-department": "IT",
        "x-role": "user",
    }
    before = client.get("/api/v1/api-keys", headers=admin_headers).json()["total"]
    resp = client.post(
        "/api/v1/api-keys/applications",
        headers=bad_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test"},
    )
    after = client.get("/api/v1/api-keys", headers=admin_headers).json()["total"]
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert before == after


def test_error_response_shape_consistency(client, admin_headers, user_headers):
    # non-whitelist application error
    e1 = client.post(
        "/api/v1/api-keys/applications",
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test"},
    )
    # non-admin whitelist management error
    e2 = client.get("/api/v1/whitelists", headers=user_headers)

    for resp in (e1, e2):
        body = resp.json()
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]


def test_admin_user_statistics_default_sort_scope_and_no_plaintext(client, admin_headers):
    user1 = build_headers(role="user", account="alice", email="alice@example.com", sysid="user-alice", name="Alice")
    user2 = build_headers(role="user", account="bob", email="bob@example.com", sysid="user-bob", name="Bob")
    _create_whitelist(client, admin_headers, user1["x-email"])
    _create_whitelist(client, admin_headers, user2["x-email"])

    for _ in range(2):
        resp = client.post(
            "/api/v1/api-keys/applications",
            headers=user1,
            json={"application_date": "2026-05-01", "duration_months": 1, "purpose": "u1"},
        )
        assert resp.status_code == 201
    resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user2,
        json={"application_date": "2026-05-02", "duration_months": 1, "purpose": "u2"},
    )
    assert resp.status_code == 201

    stats_resp = client.get("/api/v1/api-keys/statistics/users", headers=admin_headers)
    assert stats_resp.status_code == 200
    body = stats_resp.json()
    assert body["total"] == 2
    assert body["items"][0]["owner_account"] == "alice"
    assert body["items"][0]["total_applications"] == 2
    assert "api_key_plaintext" not in body["items"][0]


def test_admin_user_statistics_scope_date_range_and_forbidden(client, admin_headers):
    user = build_headers(role="user", account="carol", email="carol@example.com", sysid="user-carol", name="Carol")
    _create_whitelist(client, admin_headers, user["x-email"])

    first = client.post(
        "/api/v1/api-keys/applications",
        headers=user,
        json={"application_date": "2026-05-01", "duration_months": 1, "purpose": "first"},
    )
    second = client.post(
        "/api/v1/api-keys/applications",
        headers=user,
        json={"application_date": "2026-05-03", "duration_months": 1, "purpose": "second"},
    )
    assert first.status_code == 201
    assert second.status_code == 201

    key_id = client.get("/api/v1/api-keys", headers=user).json()["items"][0]["id"]
    revoke_resp = client.post(f"/api/v1/api-keys/{key_id}/revoke", headers=user)
    assert revoke_resp.status_code == 200

    all_resp = client.get("/api/v1/api-keys/statistics/users?scope=all", headers=admin_headers)
    active_resp = client.get("/api/v1/api-keys/statistics/users?scope=active", headers=admin_headers)
    revoked_resp = client.get("/api/v1/api-keys/statistics/users?scope=revoked", headers=admin_headers)
    expired_resp = client.get("/api/v1/api-keys/statistics/users?scope=expired", headers=admin_headers)
    ranged_resp = client.get(
        "/api/v1/api-keys/statistics/users?from=2026-05-02&to=2026-05-03",
        headers=admin_headers,
    )

    assert all_resp.status_code == 200
    assert active_resp.status_code == 200
    assert revoked_resp.status_code == 200
    assert expired_resp.status_code == 200
    assert ranged_resp.status_code == 200

    all_item = all_resp.json()["items"][0]
    active_item = active_resp.json()["items"][0]
    revoked_item = revoked_resp.json()["items"][0]
    ranged_item = ranged_resp.json()["items"][0]

    assert all_item["total_applications"] == 2
    assert active_item["total_applications"] == 1
    assert revoked_item["total_applications"] == 1
    assert expired_resp.json()["total"] == 0
    assert ranged_item["total_applications"] == 1

    forbidden = client.get("/api/v1/api-keys/statistics/users", headers=user)
    assert forbidden.status_code == 403

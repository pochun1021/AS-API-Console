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
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["issuance_status"] == "pending"
    assert body["api_key_plaintext"] is None
    assert body["pending_reason"] == "awaiting_admin_mode_selection"
    app_id = body["application"]["id"]

    mode_resp = client.patch(
        f"/api/v1/api-keys/applications/{app_id}/issuance-mode",
        headers=admin_headers,
        json={"mode": "budget"},
    )
    assert mode_resp.status_code == 200

    issue_resp = client.post(f"/api/v1/api-keys/applications/{app_id}/issue", headers=admin_headers)
    assert issue_resp.status_code == 200
    assert issue_resp.json()["api_key_plaintext"].startswith("AS-")

    list_resp = client.get("/api/v1/api-keys", headers=user_headers)
    assert list_resp.status_code == 200
    item = list_resp.json()["items"][0]
    assert "api_key_plaintext" not in item
    assert "key_prefix" not in item
    assert item["masked_key"].startswith("AS-...")
    assert item["key_alias"] == f"for_{user_headers['x-account']}"
    assert len(item["masked_key"]) == 10


def test_application_rejects_non_whitelisted(client, user_headers):
    resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test", "max_budget": "1000", "budget_duration": "monthly"},
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
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["issuance_status"] == "pending"


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
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test", "max_budget": "1000", "budget_duration": "monthly"},
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
        json={"application_date": str(date.today()), "duration_months": 2, "purpose": "test", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_DURATION_MONTHS"


def test_application_rejects_future_date(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-email"])
    resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user_headers,
        json={"application_date": "2999-01-01", "duration_months": 1, "purpose": "test", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_APPLICATION_DATE"


def test_admin_pending_flow_permissions_and_issue(client, admin_headers, user_headers, monkeypatch):
    _create_whitelist(client, admin_headers, user_headers["x-email"])
    create_resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert create_resp.status_code == 201
    app_id = create_resp.json()["application"]["id"]

    forbidden_list = client.get("/api/v1/api-keys/applications/pending", headers=user_headers)
    assert forbidden_list.status_code == 403

    pending_list = client.get("/api/v1/api-keys/applications/pending", headers=admin_headers)
    assert pending_list.status_code == 200
    assert any(item["id"] == app_id for item in pending_list.json()["items"])

    invalid_mode = client.patch(
        f"/api/v1/api-keys/applications/{app_id}/issuance-mode",
        headers=admin_headers,
        json={"mode": "invalid"},
    )
    assert invalid_mode.status_code == 422

    mode_resp = client.patch(
        f"/api/v1/api-keys/applications/{app_id}/issuance-mode",
        headers=admin_headers,
        json={"mode": "budget"},
    )
    assert mode_resp.status_code == 200

    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)

    def _raise_unavailable(self, payload):
        from app.services.provider_client import ProviderUnavailableError

        raise ProviderUnavailableError("provider unavailable")

    monkeypatch.setattr("app.services.provider_client.ProviderClient.generate_key", _raise_unavailable)
    resp = client.post(f"/api/v1/api-keys/applications/{app_id}/issue", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["issuance_status"] == "pending"
    assert body["api_key_plaintext"] is None


def test_revoke_permissions_and_status_checks(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="user-1")
    user2 = build_headers(role="user", account="user2", email="user2@example.com", sysid="user-2")

    _create_whitelist(client, admin_headers, user1["x-email"])

    create_resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user1,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test", "max_budget": "1000", "budget_duration": "monthly"},
    )
    app_id = create_resp.json()["application"]["id"]
    client.patch(f"/api/v1/api-keys/applications/{app_id}/issuance-mode", headers=admin_headers, json={"mode": "budget"})
    client.post(f"/api/v1/api-keys/applications/{app_id}/issue", headers=admin_headers)
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
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "u1", "max_budget": "1000", "budget_duration": "monthly"},
    )
    resp2 = client.post(
        "/api/v1/api-keys/applications",
        headers=user2,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "u2", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert resp1.status_code == 201
    assert resp2.status_code == 201
    app1 = resp1.json()["application"]["id"]
    app2 = resp2.json()["application"]["id"]
    client.patch(f"/api/v1/api-keys/applications/{app1}/issuance-mode", headers=admin_headers, json={"mode": "budget"})
    client.patch(f"/api/v1/api-keys/applications/{app2}/issuance-mode", headers=admin_headers, json={"mode": "budget"})
    client.post(f"/api/v1/api-keys/applications/{app1}/issue", headers=admin_headers)
    client.post(f"/api/v1/api-keys/applications/{app2}/issue", headers=admin_headers)

    admin_list = client.get("/api/v1/api-keys", headers=admin_headers)
    assert admin_list.status_code == 200
    owners = {item["owner_account"] for item in admin_list.json()["items"]}
    assert "user1" in owners
    assert "user2" in owners


def test_admin_can_filter_key_list_by_owner_status_and_date(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="user-1")
    user2 = build_headers(role="user", account="user2", email="user2@example.com", sysid="user-2")
    _create_whitelist(client, admin_headers, user1["x-email"])
    _create_whitelist(client, admin_headers, user2["x-email"])

    resp1 = client.post(
        "/api/v1/api-keys/applications",
        headers=user1,
        json={"application_date": "2026-05-01", "duration_months": 1, "purpose": "u1", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert resp1.status_code == 201
    app1 = resp1.json()["application"]["id"]
    client.patch(f"/api/v1/api-keys/applications/{app1}/issuance-mode", headers=admin_headers, json={"mode": "budget"})
    client.post(f"/api/v1/api-keys/applications/{app1}/issue", headers=admin_headers)
    key_id = client.get("/api/v1/api-keys", headers=user1).json()["items"][0]["id"]
    revoke = client.post(f"/api/v1/api-keys/{key_id}/revoke", headers=user1)
    assert revoke.status_code == 200

    resp2 = client.post(
        "/api/v1/api-keys/applications",
        headers=user1,
        json={"application_date": "2026-05-10", "duration_months": 1, "purpose": "u1-2", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert resp2.status_code == 201
    app2 = resp2.json()["application"]["id"]
    client.patch(f"/api/v1/api-keys/applications/{app2}/issuance-mode", headers=admin_headers, json={"mode": "budget"})
    client.post(f"/api/v1/api-keys/applications/{app2}/issue", headers=admin_headers)

    resp3 = client.post(
        "/api/v1/api-keys/applications",
        headers=user2,
        json={"application_date": "2026-05-03", "duration_months": 1, "purpose": "u2", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert resp3.status_code == 201
    app3 = resp3.json()["application"]["id"]
    client.patch(f"/api/v1/api-keys/applications/{app3}/issuance-mode", headers=admin_headers, json={"mode": "budget"})
    client.post(f"/api/v1/api-keys/applications/{app3}/issue", headers=admin_headers)

    filtered = client.get(
        "/api/v1/api-keys?owner_account=user1&status=active&from=2026-05-05&to=2026-05-31",
        headers=admin_headers,
    )
    assert filtered.status_code == 200
    items = filtered.json()["items"]
    assert len(items) == 1
    assert items[0]["owner_account"] == "user1"
    assert items[0]["status"] == "active"
    assert items[0]["application_date"] == "2026-05-10"


def test_reveal_plaintext_admin_only(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="user-1")
    _create_whitelist(client, admin_headers, user1["x-email"])
    create_resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user1,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "u1", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert create_resp.status_code == 201
    app_id = create_resp.json()["application"]["id"]
    client.patch(f"/api/v1/api-keys/applications/{app_id}/issuance-mode", headers=admin_headers, json={"mode": "budget"})
    issue_resp = client.post(f"/api/v1/api-keys/applications/{app_id}/issue", headers=admin_headers)
    created_plaintext = issue_resp.json()["api_key_plaintext"]
    key_id = client.get("/api/v1/api-keys", headers=user1).json()["items"][0]["id"]

    forbidden = client.post(f"/api/v1/api-keys/{key_id}/reveal", headers=user1)
    assert forbidden.status_code == 403

    reveal_resp = client.post(f"/api/v1/api-keys/{key_id}/reveal", headers=admin_headers)
    assert reveal_resp.status_code == 200
    assert reveal_resp.json()["api_key_plaintext"] == created_plaintext


def test_admin_can_update_key_alias_and_user_cannot(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="user-1")
    _create_whitelist(client, admin_headers, user1["x-email"])
    create_resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user1,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "u1", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert create_resp.status_code == 201
    app_id = create_resp.json()["application"]["id"]
    client.patch(f"/api/v1/api-keys/applications/{app_id}/issuance-mode", headers=admin_headers, json={"mode": "budget"})
    client.post(f"/api/v1/api-keys/applications/{app_id}/issue", headers=admin_headers)
    key_id = client.get("/api/v1/api-keys", headers=user1).json()["items"][0]["id"]

    forbidden = client.patch(f"/api/v1/api-keys/{key_id}", headers=user1, json={"key_alias": "custom_user_alias"})
    assert forbidden.status_code == 403

    invalid = client.patch(f"/api/v1/api-keys/{key_id}", headers=admin_headers, json={"key_alias": "   "})
    assert invalid.status_code == 422

    updated = client.patch(f"/api/v1/api-keys/{key_id}", headers=admin_headers, json={"key_alias": "custom_admin_alias"})
    assert updated.status_code == 200
    assert updated.json()["key_alias"] == "custom_admin_alias"

    listed = client.get("/api/v1/api-keys", headers=admin_headers)
    assert listed.status_code == 200
    admin_item = next(item for item in listed.json()["items"] if item["id"] == key_id)
    assert admin_item["key_alias"] == "custom_admin_alias"


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
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test", "max_budget": "1000", "budget_duration": "monthly"},
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
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test", "max_budget": "1000", "budget_duration": "monthly"},
    )
    # non-admin whitelist management error
    e2 = client.get("/api/v1/whitelists", headers=user_headers)

    for resp in (e1, e2):
        body = resp.json()
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]


def test_admin_user_statistics_default_sort_scope_and_no_plaintext(client, admin_headers):
    user1 = build_headers(
        role="user", account="alice", email="alice@example.com", sysid="user-alice", name="Alice", department="R&D"
    )
    user2 = build_headers(
        role="user", account="bob", email="bob@example.com", sysid="user-bob", name="Bob", department="Security"
    )
    _create_whitelist(client, admin_headers, user1["x-email"])
    _create_whitelist(client, admin_headers, user2["x-email"])

    for _ in range(2):
        resp = client.post(
            "/api/v1/api-keys/applications",
            headers=user1,
            json={"application_date": "2026-05-01", "duration_months": 1, "purpose": "u1", "max_budget": "1000", "budget_duration": "monthly"},
        )
        assert resp.status_code == 201
        app_id = resp.json()["application"]["id"]
        client.patch(f"/api/v1/api-keys/applications/{app_id}/issuance-mode", headers=admin_headers, json={"mode": "budget"})
        client.post(f"/api/v1/api-keys/applications/{app_id}/issue", headers=admin_headers)
    resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user2,
        json={"application_date": "2026-05-02", "duration_months": 1, "purpose": "u2", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert resp.status_code == 201
    app_id = resp.json()["application"]["id"]
    client.patch(f"/api/v1/api-keys/applications/{app_id}/issuance-mode", headers=admin_headers, json={"mode": "budget"})
    client.post(f"/api/v1/api-keys/applications/{app_id}/issue", headers=admin_headers)

    stats_resp = client.get("/api/v1/api-keys/statistics/users", headers=admin_headers)
    assert stats_resp.status_code == 200
    body = stats_resp.json()
    assert body["total"] == 2
    assert body["items"][0]["owner_account"] == "alice"
    assert body["items"][0]["owner_department"] == "R&D"
    assert body["items"][0]["total_applications"] == 2
    assert "api_key_plaintext" not in body["items"][0]


def test_admin_user_statistics_scope_date_range_and_forbidden(client, admin_headers):
    user = build_headers(role="user", account="carol", email="carol@example.com", sysid="user-carol", name="Carol")
    _create_whitelist(client, admin_headers, user["x-email"])

    first = client.post(
        "/api/v1/api-keys/applications",
        headers=user,
        json={"application_date": "2026-05-01", "duration_months": 1, "purpose": "first", "max_budget": "1000", "budget_duration": "monthly"},
    )
    second = client.post(
        "/api/v1/api-keys/applications",
        headers=user,
        json={"application_date": "2026-05-03", "duration_months": 1, "purpose": "second", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    for app_id in [first.json()["application"]["id"], second.json()["application"]["id"]]:
        client.patch(f"/api/v1/api-keys/applications/{app_id}/issuance-mode", headers=admin_headers, json={"mode": "budget"})
        client.post(f"/api/v1/api-keys/applications/{app_id}/issue", headers=admin_headers)

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

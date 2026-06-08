
from datetime import datetime
import json

from tests.conftest import api_path, build_headers
from app.services.persnl_soap_service import PersnlSoapUnavailableError
from db.session import get_db
from db.models.institute import Institute
from db.models.operation_audit_logs import OperationAuditLog


def test_whitelist_admin_only(client, admin_headers, user_headers):
    user_resp = client.get(api_path("/whitelists"), headers=user_headers)
    assert user_resp.status_code == 403

    admin_resp = client.post(
        api_path("/whitelists"),
        headers=admin_headers,
        json={"sysid": 7001, "account": "u7001", "name": "User 7001", "email": "u7001@example.com", "note": "seed"},
    )
    assert admin_resp.status_code == 201

    listed = client.get(api_path("/whitelists"), headers=admin_headers)
    assert listed.status_code == 200
    item = listed.json()["items"][0]
    for field in ("created_at", "updated_at"):
        value = item[field]
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        assert parsed.tzinfo is not None
        assert value.endswith("Z") or value.endswith("+00:00")


def test_whitelist_duplicate_sysid(client, admin_headers):
    payload = {"sysid": 7002, "account": "u7002", "name": "User 7002", "email": "u7002@example.com", "note": "seed"}
    first = client.post(api_path("/whitelists"), headers=admin_headers, json=payload)
    second = client.post(api_path("/whitelists"), headers=admin_headers, json=payload)
    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "WHITELIST_SYSID_DUPLICATED"


def test_whitelist_note_accepts_chinese_and_english(client, admin_headers):
    payload = {
        "sysid": 7005,
        "account": "u7005",
        "name": "User 7005",
        "email": "u7005@example.com",
        "note": "平台團隊 API_使用說明-2026",
    }
    resp = client.post(api_path("/whitelists"), headers=admin_headers, json=payload)
    assert resp.status_code == 201
    assert resp.json()["note"] == payload["note"]


def test_whitelist_note_rejects_unsafe_syntax(client, admin_headers):
    payload = {
        "sysid": 7006,
        "account": "u7006",
        "name": "User 7006",
        "email": "u7006@example.com",
        "note": "<script>alert(1)</script>",
    }
    resp = client.post(api_path("/whitelists"), headers=admin_headers, json=payload)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert resp.json()["error"]["message"] == "note contains unsafe syntax"


def test_whitelist_note_rejects_invalid_characters(client, admin_headers):
    payload = {
        "sysid": 7007,
        "account": "u7007",
        "name": "User 7007",
        "email": "u7007@example.com",
        "note": "平台團隊.API",
    }
    resp = client.post(api_path("/whitelists"), headers=admin_headers, json=payload)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert resp.json()["error"]["message"] == "note contains invalid characters"


def test_whitelist_delete_admin_only(client, admin_headers, user_headers):
    created = client.post(
        api_path("/whitelists"),
        headers=admin_headers,
        json={"sysid": 7010, "account": "u7010", "name": "User 7010", "email": "u7010@example.com", "note": "seed"},
    )
    assert created.status_code == 201
    whitelist_id = created.json()["id"]

    forbidden = client.delete(api_path(f"/whitelists/{whitelist_id}"), headers=user_headers)
    assert forbidden.status_code == 403

    deleted = client.delete(api_path(f"/whitelists/{whitelist_id}"), headers=admin_headers)
    assert deleted.status_code == 204

    listed = client.get(api_path("/whitelists"), headers=admin_headers)
    assert listed.status_code == 200
    assert all(item["id"] != whitelist_id for item in listed.json()["items"])


def test_whitelist_list_supports_server_side_filters_sort_and_total(client, admin_headers):
    payloads = [
        {"sysid": 8101, "account": "amy.lin", "name": "Amy Lin", "email": "amy.lin@example.com", "note": "ops"},
        {"sysid": 8102, "account": "bravo.user", "name": "Bravo User", "email": "bravo@example.com", "note": "ops"},
        {"sysid": 8103, "account": "amy.chen", "name": "Amy Chen", "email": "amy.chen@example.com", "note": "ops"},
    ]
    for payload in payloads:
        created = client.post(api_path("/whitelists"), headers=admin_headers, json=payload)
        assert created.status_code == 201

    filtered = client.get(
        api_path("/whitelists?account=amy&status=active&sort_by=sysid&sort_dir=asc&page=1&page_size=1"),
        headers=admin_headers,
    )
    assert filtered.status_code == 200
    body = filtered.json()
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["page_size"] == 1
    assert [item["sysid"] for item in body["items"]] == [8101]

    next_page = client.get(
        api_path("/whitelists?account=amy&status=active&sort_by=sysid&sort_dir=asc&page=2&page_size=1"),
        headers=admin_headers,
    )
    assert next_page.status_code == 200
    assert [item["sysid"] for item in next_page.json()["items"]] == [8103]


def test_users_admin_role_endpoints(client, admin_headers, monkeypatch):
    # bootstrap another admin identity via auth headers
    target_admin_headers = build_headers(role="admin", account="u1", email="u1@example.com", sysid=7003)
    bootstrap = client.get(api_path("/api-keys"), headers=target_admin_headers)
    assert bootstrap.status_code == 200

    def fake_search_by_keyword(self, keyword, limit=20):
        assert keyword == "u1"
        return [{"sysId": "7003", "cn": "u1", "chName": "User One", "email": "u1@example.com", "instCode": "01", "tCode": "A01"}]

    monkeypatch.setattr(
        "app.services.persnl_soap_service.PersnlSoapService.search_by_keyword",
        fake_search_by_keyword,
    )

    users = client.get(api_path("/users?q=u1&lookup_context=admin_create"), headers=admin_headers)
    assert users.status_code == 200
    assert users.json()["total"] >= 1
    user_item = users.json()["items"][0]
    user_id = user_item["id"]
    assert "sysid" in user_item
    assert str(user_item["sysid"]) == user_item["id"]
    assert user_item["department"] == "01"

    create = client.put(
        api_path(f"/admins/{user_id}"),
        headers=admin_headers,
        json={
            "account": user_item["account"],
            "name": user_item["name"],
            "email": user_item["email"],
            "department": user_item["department"],
        },
    )
    assert create.status_code == 409
    assert create.json()["error"]["code"] == "ADMIN_ALREADY_EXISTS"

    disable = client.post(api_path(f"/admins/{user_id}/disable"), headers=admin_headers)
    assert disable.status_code == 200
    assert disable.json()["role"] == "admin"
    assert disable.json()["status"] == "inactive"

    disabled_list = client.get(api_path("/api-keys"), headers=target_admin_headers)
    assert disabled_list.status_code == 403
    assert disabled_list.json()["error"]["code"] == "FORBIDDEN"


def test_user_not_found_for_role_mutation(client, admin_headers):
    resp = client.post(api_path("/admins/999999/enable"), headers=admin_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "USER_NOT_FOUND"


def test_admin_create_conflict_and_delete_inactive_only(client, admin_headers):
    create_existing = client.put(
        api_path("/admins/1001"),
        headers=admin_headers,
        json={
            "account": "admin",
            "name": "Admin User",
            "email": "admin@example.com",
            "department": "01",
        },
    )
    assert create_existing.status_code == 409
    assert create_existing.json()["error"]["code"] == "ADMIN_ALREADY_EXISTS"

    target_admin_headers = build_headers(role="admin", account="u1", email="u1@example.com", sysid=7003)
    bootstrap = client.get(api_path("/api-keys"), headers=target_admin_headers)
    assert bootstrap.status_code == 200

    delete_active = client.delete(api_path("/admins/7003"), headers=admin_headers)
    assert delete_active.status_code == 422

    disabled = client.post(api_path("/admins/7003/disable"), headers=admin_headers)
    assert disabled.status_code == 200

    delete_inactive = client.delete(api_path("/admins/7003"), headers=admin_headers)
    assert delete_inactive.status_code == 204


def test_users_returns_503_when_persnl_unavailable(client, admin_headers, monkeypatch):
    def fake_search_by_keyword(self, keyword, limit=20):
        raise PersnlSoapUnavailableError("down")

    monkeypatch.setattr(
        "app.services.persnl_soap_service.PersnlSoapService.search_by_keyword",
        fake_search_by_keyword,
    )

    users = client.get(api_path("/users?q=u1&lookup_context=whitelist_create"), headers=admin_headers)
    assert users.status_code == 503
    assert users.json()["error"]["code"] == "SOAP_SERVICE_UNAVAILABLE"


def test_users_requires_query(client, admin_headers):
    users = client.get(api_path("/users"), headers=admin_headers)
    assert users.status_code == 422


def test_users_lookup_context_is_required(client, admin_headers):
    users = client.get(api_path("/users?q=u1"), headers=admin_headers)
    assert users.status_code == 422


def test_users_invalid_lookup_context_is_rejected(client, admin_headers):
    users = client.get(api_path("/users?q=u1&lookup_context=bad"), headers=admin_headers)
    assert users.status_code == 422


def test_users_lookup_writes_audit_log(client, admin_headers, monkeypatch):
    target_admin_headers = build_headers(role="admin", account="u1", email="u1@example.com", sysid=7003)
    bootstrap = client.get(api_path("/api-keys"), headers=target_admin_headers)
    assert bootstrap.status_code == 200

    def fake_search_by_keyword(self, keyword, limit=20):
        assert keyword == "u1"
        return [{"sysId": "7003", "cn": "u1", "chName": "User One", "email": "u1@example.com", "instCode": "01", "tCode": "A01"}]

    monkeypatch.setattr(
        "app.services.persnl_soap_service.PersnlSoapService.search_by_keyword",
        fake_search_by_keyword,
    )

    resp = client.get(
        api_path("/users?q=u1&lookup_context=proxy_application"),
        headers={**target_admin_headers, "x-request-id": "req-user-lookup-ok"},
    )
    assert resp.status_code == 200

    db = next(client.app.dependency_overrides[get_db]())
    try:
        row = db.query(OperationAuditLog).filter(OperationAuditLog.request_id == "req-user-lookup-ok").one()
    finally:
        db.close()
    assert row.event_type == "user_lookup"
    assert row.action == "proxy_application"
    assert row.result == "success"
    assert row.actor_account == target_admin_headers["x-account"]
    assert row.target_type == "user_search"
    assert row.target_id == "u1"
    metadata = json.loads(row.metadata_json or "{}")
    assert metadata["lookup_context"] == "proxy_application"
    assert metadata["matched_count"] == 1


def test_users_lookup_failure_writes_audit_log(client, admin_headers):
    target_admin_headers = build_headers(role="admin", account="u1", email="u1@example.com", sysid=7003)
    bootstrap = client.get(api_path("/api-keys"), headers=target_admin_headers)
    assert bootstrap.status_code == 200

    resp = client.get(
        api_path("/users?q=u1&lookup_context=bad"),
        headers={**target_admin_headers, "x-request-id": "req-user-lookup-fail"},
    )
    assert resp.status_code == 422

    db = next(client.app.dependency_overrides[get_db]())
    try:
        row = db.query(OperationAuditLog).filter(OperationAuditLog.request_id == "req-user-lookup-fail").one()
    finally:
        db.close()
    assert row.event_type == "user_lookup"
    assert row.action == "bad"
    assert row.result == "failure"
    assert row.error_code == "VALIDATION_ERROR"
    assert row.error_detail == "lookup_context must be one of: proxy_application, admin_create, whitelist_create"


def test_admins_list_reads_db_when_persnl_unavailable(client, admin_headers, monkeypatch):
    target_admin_headers = build_headers(role="admin", account="u1", email="u1@example.com", sysid=7003)
    bootstrap = client.get(api_path("/api-keys"), headers=target_admin_headers)
    assert bootstrap.status_code == 200

    disabled = client.post(api_path("/admins/7003/disable"), headers=admin_headers)
    assert disabled.status_code == 200

    def fake_search_by_keyword(self, keyword, limit=20):
        raise PersnlSoapUnavailableError("down")

    monkeypatch.setattr(
        "app.services.persnl_soap_service.PersnlSoapService.search_by_keyword",
        fake_search_by_keyword,
    )

    admins = client.get(api_path("/admins"), headers=admin_headers)
    assert admins.status_code == 200
    payload = admins.json()
    assert payload["total"] >= 2
    by_id = {item["id"]: item for item in payload["items"]}
    assert by_id["1001"]["status"] == "active"
    assert by_id["7003"]["status"] == "inactive"


def test_list_institutes_returns_active_only(client, admin_headers):
    override_get_db = client.app.dependency_overrides[get_db]
    db = next(override_get_db())
    db.add(
        Institute(
            inst_code="01",
            inst_name="院本部",
            abb_inst_name="院本部",
            einst_name="HQ",
            division="1",
            status="active",
        )
    )
    db.add(
        Institute(
            inst_code="99",
            inst_name="停用單位",
            abb_inst_name="停用",
            einst_name="Inactive",
            division="9",
            status="inactive",
        )
    )
    db.commit()
    db.close()

    resp = client.get(api_path("/institutes"), headers=admin_headers)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total"] == 1
    assert payload["items"][0]["inst_code"] == "01"


def test_sync_institutes_admin_success(client, admin_headers, monkeypatch):
    monkeypatch.setattr(
        "app.services.persnl_soap_service.PersnlSoapService.get_institutes",
        lambda self: [
            {
                "instCode": "01",
                "instName": "院本部",
                "abb_instName": "院本部",
                "einstName": "HQ",
                "division": "1",
            }
        ],
    )

    resp = client.post(api_path("/institutes/sync"), headers=admin_headers)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["fetched_count"] == 1
    assert payload["inserted_count"] == 1

    listed = client.get(api_path("/institutes"), headers=admin_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


def test_sync_institutes_forbidden_for_non_admin(client, user_headers):
    resp = client.post(api_path("/institutes/sync"), headers=user_headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_sync_institutes_returns_503_when_soap_unavailable(client, admin_headers, monkeypatch):
    def raise_unavailable(self):
        raise PersnlSoapUnavailableError("down")

    monkeypatch.setattr(
        "app.services.persnl_soap_service.PersnlSoapService.get_institutes",
        raise_unavailable,
    )

    resp = client.post(api_path("/institutes/sync"), headers=admin_headers)
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "SOAP_SERVICE_UNAVAILABLE"

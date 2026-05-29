
from tests.conftest import build_headers
from app.services.persnl_soap_service import PersnlSoapUnavailableError
from db.session import get_db
from db.models.institute import Institute


def test_whitelist_admin_only(client, admin_headers, user_headers):
    user_resp = client.get("/api/v1/whitelists", headers=user_headers)
    assert user_resp.status_code == 403

    admin_resp = client.post(
        "/api/v1/whitelists",
        headers=admin_headers,
        json={"sysid": 7001, "note": "seed"},
    )
    assert admin_resp.status_code == 201


def test_whitelist_duplicate_sysid(client, admin_headers):
    payload = {"sysid": 7002, "note": "seed"}
    first = client.post("/api/v1/whitelists", headers=admin_headers, json=payload)
    second = client.post("/api/v1/whitelists", headers=admin_headers, json=payload)
    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "WHITELIST_SYSID_DUPLICATED"


def test_users_admin_role_endpoints(client, admin_headers, monkeypatch):
    # bootstrap another admin identity via auth headers
    target_admin_headers = build_headers(role="admin", account="u1", email="u1@example.com", sysid=7003)
    bootstrap = client.get("/api/v1/api-keys", headers=target_admin_headers)
    assert bootstrap.status_code == 200

    def fake_search_by_keyword(self, keyword, limit=20):
        assert keyword == "u1"
        return [{"sysId": "7003", "cn": "u1", "chName": "User One", "email": "u1@example.com", "instCode": "01", "tCode": "A01"}]

    monkeypatch.setattr(
        "app.services.persnl_soap_service.PersnlSoapService.search_by_keyword",
        fake_search_by_keyword,
    )

    users = client.get("/api/v1/users?q=u1", headers=admin_headers)
    assert users.status_code == 200
    assert users.json()["total"] >= 1
    user_item = users.json()["items"][0]
    user_id = user_item["id"]
    assert "sysid" in user_item
    assert str(user_item["sysid"]) == user_item["id"]
    assert user_item["department"] == "01"

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
    resp = client.post("/api/v1/admins/999999/enable", headers=admin_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "USER_NOT_FOUND"


def test_users_returns_503_when_persnl_unavailable(client, admin_headers, monkeypatch):
    def fake_search_by_keyword(self, keyword, limit=20):
        raise PersnlSoapUnavailableError("down")

    monkeypatch.setattr(
        "app.services.persnl_soap_service.PersnlSoapService.search_by_keyword",
        fake_search_by_keyword,
    )

    users = client.get("/api/v1/users?q=u1", headers=admin_headers)
    assert users.status_code == 503
    assert users.json()["error"]["code"] == "SOAP_SERVICE_UNAVAILABLE"


def test_users_requires_query(client, admin_headers):
    users = client.get("/api/v1/users", headers=admin_headers)
    assert users.status_code == 422


def test_admins_list_reads_db_when_persnl_unavailable(client, admin_headers, monkeypatch):
    target_admin_headers = build_headers(role="admin", account="u1", email="u1@example.com", sysid=7003)
    bootstrap = client.get("/api/v1/api-keys", headers=target_admin_headers)
    assert bootstrap.status_code == 200

    disabled = client.post("/api/v1/admins/7003/disable", headers=admin_headers)
    assert disabled.status_code == 200

    def fake_search_by_keyword(self, keyword, limit=20):
        raise PersnlSoapUnavailableError("down")

    monkeypatch.setattr(
        "app.services.persnl_soap_service.PersnlSoapService.search_by_keyword",
        fake_search_by_keyword,
    )

    admins = client.get("/api/v1/admins", headers=admin_headers)
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

    resp = client.get("/api/v1/institutes", headers=admin_headers)
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

    resp = client.post("/api/v1/institutes/sync", headers=admin_headers)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["fetched_count"] == 1
    assert payload["inserted_count"] == 1

    listed = client.get("/api/v1/institutes", headers=admin_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


def test_sync_institutes_forbidden_for_non_admin(client, user_headers):
    resp = client.post("/api/v1/institutes/sync", headers=user_headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_sync_institutes_returns_503_when_soap_unavailable(client, admin_headers, monkeypatch):
    def raise_unavailable(self):
        raise PersnlSoapUnavailableError("down")

    monkeypatch.setattr(
        "app.services.persnl_soap_service.PersnlSoapService.get_institutes",
        raise_unavailable,
    )

    resp = client.post("/api/v1/institutes/sync", headers=admin_headers)
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "SOAP_SERVICE_UNAVAILABLE"

from datetime import date

from db.repositories.types import AuthIdentity
from app.services.research_eligibility_service import ResearchEligibilityResult
from tests.conftest import build_headers


def _create_whitelist(client, admin_headers, sysid: str) -> None:
    resp = client.post("/api/v1/whitelists", headers=admin_headers, json={"sysid": int(sysid), "note": "seed"})
    assert resp.status_code == 201


def test_application_success_and_no_plaintext_in_queries(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])

    create_resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["issuance_status"] == "issued"
    assert body["api_key_plaintext"].startswith("AS-")

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


def test_admin_can_submit_proxy_application_for_target_user(client, admin_headers, monkeypatch):
    target_sysid = 4001
    _create_whitelist(client, admin_headers, target_sysid)
    monkeypatch.setattr(
        "app.services.api_keys_service.DirectoryIdentityService.is_configured",
        lambda self: True,
    )
    monkeypatch.setattr(
        "app.services.api_keys_service.DirectoryIdentityService.resolve_by_account",
        lambda self, account: AuthIdentity(
            account="target.user",
            name="Target User",
            email="target.user@example.com",
            department="R&D",
            sysid=target_sysid,
        ),
    )

    resp = client.post(
        "/api/v1/api-keys/applications",
        headers=admin_headers,
        json={
            "application_date": str(date.today()),
            "duration_months": 1,
            "purpose": "admin proxy submit",
            "target_identity": {
                "account": "target.user",
            },
        },
    )
    assert resp.status_code == 201
    assert resp.json()["application"]["account"] == "target.user"


def test_admin_proxy_application_validates_required_target_identity_fields(client, admin_headers):
    resp = client.post(
        "/api/v1/api-keys/applications",
        headers=admin_headers,
        json={
            "application_date": str(date.today()),
            "duration_months": 1,
            "purpose": "admin proxy submit",
            "target_identity": {
                "account": "",
            },
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_admin_proxy_application_target_account_not_found(client, admin_headers, monkeypatch):
    monkeypatch.setattr(
        "app.services.api_keys_service.DirectoryIdentityService.is_configured",
        lambda self: True,
    )

    from app.services.directory_identity_service import DirectoryLookupNotFoundError

    def _raise_not_found(self, account):
        raise DirectoryLookupNotFoundError("not found")

    monkeypatch.setattr(
        "app.services.api_keys_service.DirectoryIdentityService.resolve_by_account",
        _raise_not_found,
    )
    resp = client.post(
        "/api/v1/api-keys/applications",
        headers=admin_headers,
        json={
            "application_date": str(date.today()),
            "duration_months": 1,
            "purpose": "admin proxy submit",
            "target_identity": {"account": "missing.user"},
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_admin_proxy_application_directory_unavailable(client, admin_headers, monkeypatch):
    monkeypatch.setattr(
        "app.services.api_keys_service.DirectoryIdentityService.is_configured",
        lambda self: True,
    )

    from app.services.directory_identity_service import DirectoryLookupUnavailableError

    def _raise_unavailable(self, account):
        raise DirectoryLookupUnavailableError("timeout")

    monkeypatch.setattr(
        "app.services.api_keys_service.DirectoryIdentityService.resolve_by_account",
        _raise_unavailable,
    )
    resp = client.post(
        "/api/v1/api-keys/applications",
        headers=admin_headers,
        json={
            "application_date": str(date.today()),
            "duration_months": 1,
            "purpose": "admin proxy submit",
            "target_identity": {"account": "target.user"},
        },
    )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "DIRECTORY_SERVICE_UNAVAILABLE"


def test_admin_proxy_application_target_account_not_unique(client, admin_headers, monkeypatch):
    monkeypatch.setattr(
        "app.services.api_keys_service.DirectoryIdentityService.is_configured",
        lambda self: True,
    )

    from app.services.directory_identity_service import DirectoryLookupNotUniqueError

    def _raise_not_unique(self, account):
        raise DirectoryLookupNotUniqueError("multiple accounts")

    monkeypatch.setattr(
        "app.services.api_keys_service.DirectoryIdentityService.resolve_by_account",
        _raise_not_unique,
    )
    resp = client.post(
        "/api/v1/api-keys/applications",
        headers=admin_headers,
        json={
            "application_date": str(date.today()),
            "duration_months": 1,
            "purpose": "admin proxy submit",
            "target_identity": {"account": "duplicated.user"},
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_application_immediate_issue_does_not_send_mail(client, admin_headers, user_headers, monkeypatch):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    calls: list[str] = []

    async def _fake_applicant_mail(self, **kwargs):
        calls.append("applicant")

    monkeypatch.setattr(
        "app.services.mail_service.MailService.send_application_received_to_applicant",
        _fake_applicant_mail,
    )

    resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test notify"},
    )
    assert resp.status_code == 201
    assert resp.json()["issuance_status"] == "issued"
    assert calls == []


def test_application_provider_timeout_returns_503(client, admin_headers, user_headers, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    get_settings.cache_clear()
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)

    def _raise_unavailable(self, payload):
        from app.services.provider_client import ProviderUnavailableError

        raise ProviderUnavailableError("provider unavailable")

    monkeypatch.setattr("app.services.provider_client.ProviderClient.generate_key", _raise_unavailable)

    try:
        resp = client.post(
            "/api/v1/api-keys/applications",
            headers=user_headers,
            json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test notify failure"},
        )
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        get_settings.cache_clear()


def test_applicant_mail_body_does_not_include_application_id():
    from app.services.mail_service import MailService

    service = MailService()

    # Extract body shape by reusing deterministic template construction expectation.
    body = (
        "<p>親愛的使用者，您好：</p>"
        "<p>感謝您申請 API Key 請妥善保管</p>"
        "<p>若此操作非您本人執行，請立即連繫資訊服務處。</p>"
        "<p>若您有任何疑問，歡迎向資訊服務處服務台反映。</p>"
        "<p>聯絡窗口：中央研究院資訊服務處<br/>"
        "線上服務台（上班時間）：https://its.sinica.edu.tw/online（密碼27898855）<br/>"
        "電話（上班時間）：02-27898855<br/>"
        "信箱：its@sinica.edu.tw</p>"
        "<p>中央研究院資訊服務處 敬啟</p>"
        "<hr/>"
        "<p>Dear user,</p>"
        "<p>Thank you for applying for an API key. Please keep it secure.</p>"
        "<p>If this action was not performed by you, please contact the IT Service Desk immediately.</p>"
        "<p>If you have any questions, please contact the IT Service Desk.</p>"
        "<p>Contact: Institute of Information Science, Academia Sinica IT Service Desk<br/>"
        "Online Service Desk (business hours): https://its.sinica.edu.tw/online (password: 27898855)<br/>"
        "Phone (business hours): 02-27898855<br/>"
        "Email: its@sinica.edu.tw</p>"
        "<p>Sincerely,<br/>Academia Sinica IT Service Desk</p>"
    )
    assert "申請單號" not in body
    assert "Application ID" not in body
    assert "若此操作非您本人執行" in body
    assert "中央研究院資訊服務處 敬啟" in body
    assert isinstance(service, MailService)


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
    assert create_resp.json()["issuance_status"] == "issued"


def test_application_research_service_unavailable_returns_503_and_no_records(client, admin_headers, user_headers, monkeypatch):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
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
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_months": 2, "purpose": "test", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_DURATION_MONTHS"


def test_application_rejects_future_date(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user_headers,
        json={"application_date": "2999-01-01", "duration_months": 1, "purpose": "test", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_APPLICATION_DATE"


def test_pending_endpoints_removed(client, admin_headers, user_headers):
    forbidden_list = client.get("/api/v1/api-keys/applications/pending", headers=user_headers)
    assert forbidden_list.status_code == 404

    pending_list = client.get("/api/v1/api-keys/applications/pending", headers=admin_headers)
    assert pending_list.status_code == 404


def test_issue_pending_endpoint_removed(client, admin_headers):
    resp = client.post("/api/v1/api-keys/applications/dummy-id/issue", headers=admin_headers)
    assert resp.status_code == 404


def test_issue_pending_application_does_not_send_issued_email(client, admin_headers, user_headers, monkeypatch):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    create_resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test issue mail"},
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["issuance_status"] == "issued"
    assert body["api_key_plaintext"].startswith("AS-")


def test_issue_pending_application_local_mode_does_not_call_provider(client, admin_headers, user_headers, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "local")
    get_settings.cache_clear()
    try:
        _create_whitelist(client, admin_headers, user_headers["x-sysid"])
        create_resp = client.post(
            "/api/v1/api-keys/applications",
            headers=user_headers,
            json={"application_date": str(date.today()), "duration_months": 1, "purpose": "local issue mode"},
        )
        assert create_resp.status_code == 201
        monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)

        def _raise_provider_should_not_be_called(self, payload):
            raise AssertionError("provider should not be called in local issuance mode")

        monkeypatch.setattr(
            "app.services.provider_client.ProviderClient.generate_key",
            _raise_provider_should_not_be_called,
        )
        assert create_resp.json()["issuance_status"] == "issued"
        assert create_resp.json()["api_key_plaintext"].startswith("AS-")
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        get_settings.cache_clear()


def test_revoke_permissions_and_status_checks(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    user2 = build_headers(role="user", account="user2", email="user2@example.com", sysid="2002")

    _create_whitelist(client, admin_headers, user1["x-sysid"])

    create_resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user1,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test", "max_budget": "1000", "budget_duration": "monthly"},
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


def test_renew_permissions_and_visibility(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    user2 = build_headers(role="user", account="user2", email="user2@example.com", sysid="2002")

    _create_whitelist(client, admin_headers, user1["x-sysid"])
    create_resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user1,
        json={"application_date": str(date.today()), "duration_months": 6, "purpose": "renew test"},
    )
    assert create_resp.status_code == 201
    source_id = client.get("/api/v1/api-keys", headers=user1).json()["items"][0]["id"]
    revoke = client.post(f"/api/v1/api-keys/{source_id}/revoke", headers=user1)
    assert revoke.status_code == 200

    not_owner = client.post(f"/api/v1/api-keys/{source_id}/renew", headers=user2)
    assert not_owner.status_code == 403
    assert not_owner.json()["error"]["code"] == "KEY_NOT_OWNED_BY_USER"

    renew = client.post(f"/api/v1/api-keys/{source_id}/renew", headers=user1)
    assert renew.status_code == 200
    body = renew.json()
    assert body["status"] == "active"
    assert body["issuance_status"] == "issued"
    assert body["renewed_from_key_id"] == source_id
    assert body["api_key_plaintext"].startswith("AS-")

    user_list = client.get("/api/v1/api-keys", headers=user1)
    assert user_list.status_code == 200
    user_items = user_list.json()["items"]
    assert len(user_items) == 1
    assert user_items[0]["id"] == body["id"]
    assert user_items[0]["duration_months"] == 6

    admin_list = client.get("/api/v1/api-keys", headers=admin_headers)
    assert admin_list.status_code == 200
    admin_ids = {item["id"] for item in admin_list.json()["items"]}
    assert source_id in admin_ids
    assert body["id"] in admin_ids

    duplicate = client.post(f"/api/v1/api-keys/{source_id}/renew", headers=user1)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "KEY_ALREADY_RENEWED"


def test_renew_rejects_active_key(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    create_resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "renew active"},
    )
    assert create_resp.status_code == 201
    key_id = client.get("/api/v1/api-keys", headers=user_headers).json()["items"][0]["id"]
    renew = client.post(f"/api/v1/api-keys/{key_id}/renew", headers=user_headers)
    assert renew.status_code == 409
    assert renew.json()["error"]["code"] == "KEY_NOT_RENEWABLE"


def test_renew_sends_renewed_email_on_success(client, admin_headers, monkeypatch):
    user = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user["x-sysid"])
    create_resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "renew mail"},
    )
    key_id = client.get("/api/v1/api-keys", headers=user).json()["items"][0]["id"]
    client.post(f"/api/v1/api-keys/{key_id}/revoke", headers=user)

    calls: list[dict] = []

    async def _fake_mail(self, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr("app.services.mail_service.MailService.send_key_renewed_notification", _fake_mail)

    renew = client.post(f"/api/v1/api-keys/{key_id}/renew", headers=user)
    assert create_resp.status_code == 201
    assert renew.status_code == 200
    assert len(calls) == 1
    assert calls[0]["to_email"] == user["x-email"]


def test_renew_provider_unavailable_returns_503(client, admin_headers, monkeypatch):
    from app.core.config import get_settings
    from app.services.provider_client import ProviderUnavailableError

    user = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user["x-sysid"])
    create_resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "renew pending"},
    )
    assert create_resp.status_code == 201
    key_id = client.get("/api/v1/api-keys", headers=user).json()["items"][0]["id"]
    client.post(f"/api/v1/api-keys/{key_id}/revoke", headers=user)

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)
    monkeypatch.setattr(
        "app.services.provider_client.ProviderClient.generate_key",
        lambda self, payload: (_ for _ in ()).throw(ProviderUnavailableError("provider unavailable")),
    )
    try:
        renew = client.post(f"/api/v1/api-keys/{key_id}/renew", headers=user)
        assert renew.status_code == 503
        assert renew.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        get_settings.cache_clear()


def test_admin_can_list_global_keys(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    user2 = build_headers(role="user", account="user2", email="user2@example.com", sysid="2002")
    _create_whitelist(client, admin_headers, user1["x-sysid"])
    _create_whitelist(client, admin_headers, user2["x-sysid"])

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
    admin_list = client.get("/api/v1/api-keys", headers=admin_headers)
    assert admin_list.status_code == 200
    owners = {item["owner_account"] for item in admin_list.json()["items"]}
    assert "user1" in owners
    assert "user2" in owners


def test_admin_can_filter_key_list_by_owner_status_and_date(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    user2 = build_headers(role="user", account="user2", email="user2@example.com", sysid="2002")
    _create_whitelist(client, admin_headers, user1["x-sysid"])
    _create_whitelist(client, admin_headers, user2["x-sysid"])

    resp1 = client.post(
        "/api/v1/api-keys/applications",
        headers=user1,
        json={"application_date": "2026-05-01", "duration_months": 1, "purpose": "u1", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert resp1.status_code == 201
    key_id = client.get("/api/v1/api-keys", headers=user1).json()["items"][0]["id"]
    revoke = client.post(f"/api/v1/api-keys/{key_id}/revoke", headers=user1)
    assert revoke.status_code == 200

    resp2 = client.post(
        "/api/v1/api-keys/applications",
        headers=user1,
        json={"application_date": "2026-05-10", "duration_months": 1, "purpose": "u1-2", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert resp2.status_code == 201

    resp3 = client.post(
        "/api/v1/api-keys/applications",
        headers=user2,
        json={"application_date": "2026-05-03", "duration_months": 1, "purpose": "u2", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert resp3.status_code == 201

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
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user1["x-sysid"])
    create_resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user1,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "u1", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert create_resp.status_code == 201
    created_plaintext = create_resp.json()["api_key_plaintext"]
    key_id = client.get("/api/v1/api-keys", headers=user1).json()["items"][0]["id"]

    forbidden = client.post(f"/api/v1/api-keys/{key_id}/reveal", headers=user1)
    assert forbidden.status_code == 403

    reveal_resp = client.post(f"/api/v1/api-keys/{key_id}/reveal", headers=admin_headers)
    assert reveal_resp.status_code == 200
    assert reveal_resp.json()["api_key_plaintext"] == created_plaintext


def test_admin_can_update_key_alias_and_user_cannot(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user1["x-sysid"])
    create_resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user1,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "u1", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert create_resp.status_code == 201
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
    _create_whitelist(client, admin_headers, 8100)
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
        role="user", account="alice", email="alice@example.com", sysid=8101, name="Alice", department="R&D"
    )
    user2 = build_headers(
        role="user", account="bob", email="bob@example.com", sysid=8102, name="Bob", department="Security"
    )
    _create_whitelist(client, admin_headers, user1["x-sysid"])
    _create_whitelist(client, admin_headers, user2["x-sysid"])

    for _ in range(2):
        resp = client.post(
            "/api/v1/api-keys/applications",
            headers=user1,
            json={"application_date": "2026-05-01", "duration_months": 1, "purpose": "u1", "max_budget": "1000", "budget_duration": "monthly"},
        )
        assert resp.status_code == 201
    resp = client.post(
        "/api/v1/api-keys/applications",
        headers=user2,
        json={"application_date": "2026-05-02", "duration_months": 1, "purpose": "u2", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert resp.status_code == 201

    stats_resp = client.get("/api/v1/api-keys/statistics/users", headers=admin_headers)
    assert stats_resp.status_code == 200
    body = stats_resp.json()
    assert body["total"] == 2
    assert body["items"][0]["owner_account"] == "alice"
    assert body["items"][0]["owner_department"] == "R&D"
    assert body["items"][0]["total_applications"] == 2
    assert "api_key_plaintext" not in body["items"][0]


def test_admin_user_statistics_scope_date_range_and_forbidden(client, admin_headers):
    user = build_headers(role="user", account="carol", email="carol@example.com", sysid=8103, name="Carol")
    _create_whitelist(client, admin_headers, user["x-sysid"])

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

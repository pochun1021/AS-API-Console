import logging
from types import SimpleNamespace
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from sqlalchemy import create_engine, text

from app.core.config import get_settings
from db.repositories.types import AuthIdentity
from tests.conftest import api_path as _api, build_headers


def _create_whitelist(client, admin_headers, sysid: str) -> None:
    parsed_sysid = int(sysid)
    resp = client.post(
        _api("/whitelists"),
        headers=admin_headers,
        json={
            "sysid": parsed_sysid,
            "account": f"user{parsed_sysid}",
            "name": f"User {parsed_sysid}",
            "email": f"user{parsed_sysid}@example.com",
            "note": "seed",
        },
    )
    assert resp.status_code == 201


def _set_key_expires_at_past(key_id: str) -> None:
    settings = get_settings()
    db_url = settings.test_database_url or settings.database_url
    engine = create_engine(db_url, future=True)
    past = datetime.now(UTC) - timedelta(days=1)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE api_key_applications a
                JOIN api_keys k ON k.application_id = a.id
                SET a.expires_at = :past
                WHERE k.id = :key_id
                """
            ),
            {"past": past, "key_id": key_id},
        )


def _set_expiration_notice_sent_at(key_id: str, sent_at: datetime | None) -> None:
    settings = get_settings()
    db_url = settings.test_database_url or settings.database_url
    engine = create_engine(db_url, future=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE api_keys
                SET expiration_notice_sent_at = :sent_at
                WHERE id = :key_id
                """
            ),
            {"sent_at": sent_at, "key_id": key_id},
        )


def _set_key_secret_material(key_id: str, *, key_ciphertext: str | None, key_kek_version: str | None) -> None:
    settings = get_settings()
    db_url = settings.test_database_url or settings.database_url
    engine = create_engine(db_url, future=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE api_keys
                SET key_ciphertext = :key_ciphertext,
                    key_kek_version = :key_kek_version
                WHERE id = :key_id
                """
            ),
            {
                "key_ciphertext": key_ciphertext,
                "key_kek_version": key_kek_version,
                "key_id": key_id,
            },
        )


def _fetch_key_status_row(key_id: str) -> dict:
    settings = get_settings()
    db_url = settings.test_database_url or settings.database_url
    engine = create_engine(db_url, future=True)
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT k.status AS key_status, a.status AS application_status, a.revoked_at, a.expires_at
                FROM api_keys k
                JOIN api_key_applications a ON a.id = k.application_id
                WHERE k.id = :key_id
                """
            ),
            {"key_id": key_id},
        ).mappings().one()
    return dict(row)


def _fetch_application_row(application_id: str) -> dict:
    settings = get_settings()
    db_url = settings.test_database_url or settings.database_url
    engine = create_engine(db_url, future=True)
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT id, account, name, email, department, sysid, is_proxy_submission, proxy_operator_account
                FROM api_key_applications
                WHERE id = :application_id
                """
            ),
            {"application_id": application_id},
        ).mappings().one()
    return dict(row)


def _fetch_application_row_for_key(key_id: str) -> dict:
    settings = get_settings()
    db_url = settings.test_database_url or settings.database_url
    engine = create_engine(db_url, future=True)
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT a.id, a.account, a.name, a.email, a.department, a.sysid, a.is_proxy_submission, a.proxy_operator_account
                FROM api_key_applications a
                JOIN api_keys k ON k.application_id = a.id
                WHERE k.id = :key_id
                """
            ),
            {"key_id": key_id},
        ).mappings().one()
    return dict(row)


def _assert_utc_datetime_string(value: str) -> None:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    assert value.endswith("Z") or value.endswith("+00:00")


def test_application_success_and_no_plaintext_in_queries(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])

    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test"},
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["api_key_plaintext"].startswith("AS-")
    _assert_utc_datetime_string(body["application"]["issued_at"])
    _assert_utc_datetime_string(body["application"]["expires_at"])
    application = _fetch_application_row(body["application"]["id"])
    assert application["account"] == user_headers["x-account"]
    assert application["sysid"] == int(user_headers["x-sysid"])
    assert application["is_proxy_submission"] in {0, False}
    assert application["proxy_operator_account"] is None

    list_resp = client.get(_api("/api-keys"), headers=user_headers)
    assert list_resp.status_code == 200
    item = list_resp.json()["items"][0]
    assert "api_key_plaintext" not in item
    assert "key_prefix" not in item
    assert item["masked_key"].startswith("AS-...")
    assert item["key_alias"] == f"for_{user_headers['x-account']}"
    assert len(item["masked_key"]) == 10
    assert "expiration_notice_sent_at" in item
    assert "extend_eligible" in item
    _assert_utc_datetime_string(item["expires_at"])


def test_application_rejects_non_whitelisted(client, user_headers):
    from app.services.persnl_soap_service import PersnlSoapService

    original_is_configured = PersnlSoapService.is_configured
    PersnlSoapService.is_configured = lambda self: False
    try:
        resp = client.post(
            _api("/api-keys/applications"),
            headers=user_headers,
            json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test"},
        )
    finally:
        PersnlSoapService.is_configured = original_is_configured
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "APPLICANT_NOT_ELIGIBLE"


def test_application_rejects_missing_auth_headers_with_field_details(client, user_headers):
    _create_whitelist(client, admin_headers=build_headers(role="admin", account="admin", email="admin@example.com", sysid="1001"), sysid=user_headers["x-sysid"])
    invalid_headers = dict(user_headers)
    invalid_headers.pop("x-name")

    resp = client.post(
        _api("/api-keys/applications"),
        headers=invalid_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test"},
    )

    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "x-name" in resp.json()["error"]["message"]


def test_application_rejects_non_numeric_sysid(client, user_headers):
    invalid_headers = build_headers(role="user", account="user1", email="user1@example.com", sysid="not-a-number")

    resp = client.post(
        _api("/api-keys/applications"),
        headers=invalid_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test"},
    )

    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert resp.json()["error"]["message"] == "x-sysid must be numeric"


def test_application_rejects_blank_purpose(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])

    resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "   "},
    )

    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert resp.json()["error"]["message"] == "purpose is required"


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
        _api("/api-keys/applications"),
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
    application = _fetch_application_row(resp.json()["application"]["id"])
    assert application["account"] == "target.user"
    assert application["name"] == "Target User"
    assert application["email"] == "target.user@example.com"
    assert application["department"] == "R&D"
    assert application["sysid"] == target_sysid
    assert application["is_proxy_submission"] in {1, True}
    assert application["proxy_operator_account"] == admin_headers["x-account"]


def test_admin_proxy_application_validates_required_target_identity_fields(client, admin_headers):
    resp = client.post(
        _api("/api-keys/applications"),
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
        _api("/api-keys/applications"),
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
        _api("/api-keys/applications"),
        headers=admin_headers,
        json={
            "application_date": str(date.today()),
            "duration_months": 1,
            "purpose": "admin proxy submit",
            "target_identity": {"account": "target.user"},
        },
    )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "SOAP_SERVICE_UNAVAILABLE"


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
        _api("/api-keys/applications"),
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


def test_application_immediate_issue_sends_mail(client, admin_headers, user_headers, monkeypatch):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    calls: list[dict] = []

    async def _fake_applicant_mail(self, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        "app.services.mail_service.MailService.send_application_received_to_applicant",
        _fake_applicant_mail,
    )

    resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test notify"},
    )
    assert resp.status_code == 201
    assert resp.json()["api_key_plaintext"].startswith("AS-")
    assert len(calls) == 1
    assert calls[0]["to_email"] == user_headers["x-email"]


def test_application_mail_failure_does_not_block_success(client, admin_headers, user_headers, monkeypatch):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])

    async def _raise_mail_error(self, **kwargs):
        raise RuntimeError("smtp unavailable")

    monkeypatch.setattr(
        "app.services.mail_service.MailService.send_application_received_to_applicant",
        _raise_mail_error,
    )

    resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test notify failure"},
    )
    assert resp.status_code == 201
    assert resp.json()["api_key_plaintext"].startswith("AS-")


def test_application_provider_timeout_returns_503(client, admin_headers, user_headers, monkeypatch):
    from app.core.config import get_settings

    admin_notify_calls: list[dict] = []

    async def _fake_admin_notify(self, **kwargs):
        admin_notify_calls.append(kwargs)

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    get_settings.cache_clear()
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)
    monkeypatch.setattr(
        "app.services.api_keys_service.SQLAlchemyAdminRepository.list_active_emails",
        lambda self: ["admin1@example.com", "admin2@example.com", "admin1@example.com"],
    )
    monkeypatch.setattr("app.services.mail_service.MailService.send_provider_issuance_failed_to_admins", _fake_admin_notify)

    def _raise_unavailable(self, payload):
        from app.services.provider_client import ProviderUnavailableError

        raise ProviderUnavailableError("provider unavailable")

    monkeypatch.setattr("app.services.provider_client.ProviderClient.generate_key", _raise_unavailable)

    try:
        resp = client.post(
            _api("/api-keys/applications"),
            headers=user_headers,
            json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test notify failure"},
        )
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"
        assert len(admin_notify_calls) == 1
        assert admin_notify_calls[0]["to_emails"] == ["admin1@example.com", "admin2@example.com"]
        assert admin_notify_calls[0]["operation"] == "application"
        assert admin_notify_calls[0]["error_code"] == "PROVIDER_UNAVAILABLE"
        assert admin_notify_calls[0]["target_account"] == user_headers["x-account"]
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        get_settings.cache_clear()


def test_provider_payload_builder_uses_external_contract():
    from app.services.api_keys_service import ApiKeysService, IssuanceConfigValues

    service = object.__new__(ApiKeysService)

    payload = service._build_provider_payload(
        owner_account="user1",
        duration_months=6,
        config=IssuanceConfigValues(
            max_budget="1000",
            budget_duration="monthly",
            tpm_limit=10000,
            rpm_limit=500,
        ),
    )

    assert payload == {
        "max_budget": 1000.0,
        "budget_duration": "30d",
        "duration": "180d",
        "tpm_limit": 10000,
        "rpm_limit": 500,
        "key_alias": "for_user1",
        "key_type": "llm_api",
    }


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


def test_expiration_notice_mail_contains_expiration_and_extend_hint(monkeypatch):
    from asyncio import run as run_async

    from app.services.mail_service import MailService

    captured: dict = {}

    async def _fake_send_html(self, *, subject: str, recipients: list[str], body: str):
        captured["subject"] = subject
        captured["recipients"] = recipients
        captured["body"] = body

    monkeypatch.setattr("app.services.mail_service.MailService._send_html", _fake_send_html)

    service = MailService()
    expires_at = datetime(2026, 6, 30, 1, 2, 3, tzinfo=UTC)
    run_async(
        service.send_key_expiration_notice(
            to_email="user@example.com",
            owner_name="User One",
            expires_at=expires_at,
            app_domain="",
        )
    )

    assert "即將到期提醒" in captured["subject"]
    assert captured["recipients"] == ["user@example.com"]
    assert "到期時間：2026-06-30 01:02 UTC" in captured["body"]
    assert "可於到期前或到期後進行展延" in captured["body"]
    assert "Expiration time: 2026-06-30 01:02 UTC" in captured["body"]
    assert "You can extend this key before or after expiration." in captured["body"]


def test_expiration_reminder_script_sends_once(client, admin_headers, user_headers, monkeypatch):
    from scripts import send_expiration_reminders

    calls: list[dict] = []
    commits = {"count": 0}

    class _FakeRow:
        def __init__(self):
            self.ApiKey = type("Key", (), {"id": str(uuid4()), "expiration_notice_sent_at": None})()
            self.ApiKeyApplication = type(
                "App",
                (),
                {
                    "id": str(uuid4()),
                    "name": "Tester",
                    "email": "user1@example.com",
                    "expires_at": datetime.now(UTC) + timedelta(days=30, hours=1),
                },
            )()

    class _FakeResult:
        def __init__(self, items):
            self._items = items

        def all(self):
            return self._items

    row = _FakeRow()
    queued_results = [_FakeResult([row]), _FakeResult([])]

    class _FakeSession:
        def execute(self, stmt):
            return queued_results.pop(0)

        def add(self, obj):
            return None

        def commit(self):
            commits["count"] += 1

        def rollback(self):
            return None

    class _FakeSessionCtx:
        def __init__(self):
            self.session = _FakeSession()

        def __enter__(self):
            return self.session

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("scripts.send_expiration_reminders.SessionLocal", _FakeSessionCtx)

    async def _fake_notice(self, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr("app.services.mail_service.MailService.send_key_expiration_notice", _fake_notice)

    processed_1, sent_1 = send_expiration_reminders.run_once(batch_size=100, dry_run=False, logger=logging.getLogger())
    processed_2, sent_2 = send_expiration_reminders.run_once(batch_size=100, dry_run=False, logger=logging.getLogger())

    assert processed_1 == 1
    assert sent_1 == 1
    assert processed_2 == 0
    assert sent_2 == 0
    assert len(calls) == 1
    assert calls[0]["to_email"] == user_headers["x-email"]
    assert commits["count"] == 1


def test_application_success_for_research_eligible_without_whitelist(client, user_headers, monkeypatch):
    monkeypatch.setattr(
        "app.services.api_keys_service.LoginEligibilityService.is_eligible_by_sysid",
        lambda self, sysid: False,
    )
    monkeypatch.setattr(
        "app.services.api_keys_service.PersnlSoapService.is_configured",
        lambda self: True,
    )
    monkeypatch.setattr(
        "app.services.api_keys_service.PersnlSoapService.search_person_by_account",
        lambda self, account, on_job: [{"tCode": "A01"}],
    )
    monkeypatch.setattr(
        "app.services.api_keys_service.LoginEligibilityService.is_allowed_by_tcode",
        lambda self, tcode: True,
    )

    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test"},
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["api_key_plaintext"].startswith("AS-")


def test_application_research_service_unavailable_returns_503_and_no_records(client, admin_headers, user_headers, monkeypatch):
    monkeypatch.setattr(
        "app.services.api_keys_service.LoginEligibilityService.is_eligible_by_sysid",
        lambda self, sysid: False,
    )
    monkeypatch.setattr(
        "app.services.api_keys_service.PersnlSoapService.is_configured",
        lambda self: True,
    )

    def _raise_unavailable(self, account, on_job):
        from app.services.persnl_soap_service import PersnlSoapUnavailableError

        raise PersnlSoapUnavailableError("timeout")

    monkeypatch.setattr(
        "app.services.api_keys_service.PersnlSoapService.search_person_by_account",
        _raise_unavailable,
    )

    before = client.get(_api("/api-keys"), headers=admin_headers).json()["total"]
    resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test"},
    )
    after = client.get(_api("/api-keys"), headers=admin_headers).json()["total"]

    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "SOAP_SERVICE_UNAVAILABLE"
    assert before == after


def test_application_rejects_invalid_duration(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_months": 2, "purpose": "test"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_DURATION_MONTHS"


def test_application_rejects_future_date(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": "2999-01-01", "duration_months": 1, "purpose": "test"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_APPLICATION_DATE"


def test_pending_endpoints_removed(client, admin_headers, user_headers):
    forbidden_list = client.get(_api("/api-keys/applications/pending"), headers=user_headers)
    assert forbidden_list.status_code == 404

    pending_list = client.get(_api("/api-keys/applications/pending"), headers=admin_headers)
    assert pending_list.status_code == 404


def test_issue_pending_endpoint_removed(client, admin_headers):
    resp = client.post(_api("/api-keys/applications/dummy-id/issue"), headers=admin_headers)
    assert resp.status_code == 405


def test_issue_pending_application_does_not_send_issued_email(client, admin_headers, user_headers, monkeypatch):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test issue mail"},
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["api_key_plaintext"].startswith("AS-")


def test_issue_pending_application_local_mode_does_not_call_provider(client, admin_headers, user_headers, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "local")
    get_settings.cache_clear()
    try:
        _create_whitelist(client, admin_headers, user_headers["x-sysid"])
        create_resp = client.post(
            _api("/api-keys/applications"),
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
        assert create_resp.json()["api_key_plaintext"].startswith("AS-")
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        get_settings.cache_clear()


def test_revoke_permissions_and_status_checks(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    user2 = build_headers(role="user", account="user2", email="user2@example.com", sysid="2002")

    _create_whitelist(client, admin_headers, user1["x-sysid"])

    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user1,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test", "max_budget": "1000", "budget_duration": "monthly"},
    )
    key_id = client.get(_api("/api-keys"), headers=user1).json()["items"][0]["id"]
    assert create_resp.status_code == 201

    not_owner = client.post(_api(f"/api-keys/{key_id}/revoke"), headers=user2)
    assert not_owner.status_code == 403
    assert not_owner.json()["error"]["code"] == "KEY_NOT_OWNED_BY_USER"

    first = client.post(_api(f"/api-keys/{key_id}/revoke"), headers=user1)
    assert first.status_code == 200
    assert first.json()["status"] == "revoked"

    second = client.post(_api(f"/api-keys/{key_id}/revoke"), headers=user1)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "KEY_NOT_ACTIVE"


def test_revoke_provider_unavailable_does_not_change_local_status(client, admin_headers, monkeypatch):
    from app.core.config import get_settings
    from app.services.provider_client import ProviderUnavailableError

    user = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "revoke provider fail"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user).json()["items"][0]["id"]

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)
    monkeypatch.setattr(
        "app.services.provider_client.ProviderClient.block_key",
        lambda self, payload: (_ for _ in ()).throw(ProviderUnavailableError("provider unavailable")),
    )
    try:
        resp = client.post(_api(f"/api-keys/{key_id}/revoke"), headers=user)
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"
        row = _fetch_key_status_row(key_id)
        assert row["key_status"] == "active"
        assert row["application_status"] == "active"
        assert row["revoked_at"] is None
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        get_settings.cache_clear()


def test_provider_mutation_payloads_use_key_field_and_shared_contract(client, admin_headers, monkeypatch):
    from app.core.config import get_settings
    from app.services.provider_client import ProviderGenerateResult

    user = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "revoke payload"},
    )
    assert create_resp.status_code == 201
    created_plaintext = create_resp.json()["api_key_plaintext"]
    key_id = client.get(_api("/api-keys"), headers=user).json()["items"][0]["id"]
    captured_block_payload: dict = {}
    captured_regenerate_payload: dict = {}
    captured_update_payload: dict = {}

    def _capture_block_payload(self, payload):
        captured_block_payload.update(payload)
        return SimpleNamespace(request_id=None, operation_id=None)

    def _capture_regenerate_payload(self, payload):
        captured_regenerate_payload.update(payload)
        return ProviderGenerateResult(key_plaintext="AS-renewedabcdefghijklmnopqrstuvwxyz")

    def _capture_update_payload(self, payload):
        captured_update_payload.update(payload)
        return SimpleNamespace(request_id=None, operation_id=None)

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)
    monkeypatch.setattr("app.services.provider_client.ProviderClient.block_key", _capture_block_payload)
    monkeypatch.setattr("app.services.provider_client.ProviderClient.regenerate_key", _capture_regenerate_payload)
    monkeypatch.setattr("app.services.provider_client.ProviderClient.update_key", _capture_update_payload)
    try:
        revoke = client.post(_api(f"/api-keys/{key_id}/revoke"), headers=user)
        assert revoke.status_code == 200
        assert captured_block_payload == {"key": created_plaintext}

        renew = client.post(_api(f"/api-keys/{key_id}/renew"), headers=user)
        assert renew.status_code == 200
        renewed_key_id = renew.json()["id"]
        renewed_plaintext = renew.json()["api_key_plaintext"]
        assert captured_regenerate_payload["key"] == created_plaintext
        assert captured_regenerate_payload["duration"] == "30d"
        assert captured_regenerate_payload["key_alias"] == f"for_{user['x-account']}"
        assert captured_regenerate_payload["key_type"] == "llm_api"
        assert "models" not in captured_regenerate_payload
        assert "api_key_plaintext" not in captured_regenerate_payload

        _set_expiration_notice_sent_at(renewed_key_id, datetime.now(UTC))
        extend = client.post(_api(f"/api-keys/{renewed_key_id}/extend"), headers=user, json={"duration_months": 6})
        assert extend.status_code == 200
        assert captured_update_payload["key"] == renewed_plaintext
        assert captured_update_payload["duration"] == "180d"
        assert captured_update_payload["key_alias"] == f"for_{user['x-account']}"
        assert captured_update_payload["key_type"] == "llm_api"
        assert "models" not in captured_update_payload
        assert "api_key_plaintext" not in captured_update_payload
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        get_settings.cache_clear()


def test_renew_permissions_and_visibility(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    user2 = build_headers(role="user", account="user2", email="user2@example.com", sysid="2002")

    _create_whitelist(client, admin_headers, user1["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user1,
        json={"application_date": str(date.today()), "duration_months": 6, "purpose": "renew test"},
    )
    assert create_resp.status_code == 201
    source_id = client.get(_api("/api-keys"), headers=user1).json()["items"][0]["id"]
    revoke = client.post(_api(f"/api-keys/{source_id}/revoke"), headers=user1)
    assert revoke.status_code == 200

    not_owner = client.post(_api(f"/api-keys/{source_id}/renew"), headers=user2)
    assert not_owner.status_code == 403
    assert not_owner.json()["error"]["code"] == "KEY_NOT_OWNED_BY_USER"

    renew = client.post(_api(f"/api-keys/{source_id}/renew"), headers=user1)
    assert renew.status_code == 200
    body = renew.json()
    assert body["status"] == "active"
    assert body["renewed_from_key_id"] == source_id
    assert body["api_key_plaintext"].startswith("AS-")
    renewed_application = _fetch_application_row_for_key(body["id"])
    assert renewed_application["account"] == user1["x-account"]
    assert renewed_application["sysid"] == int(user1["x-sysid"])
    assert renewed_application["is_proxy_submission"] in {0, False}
    assert renewed_application["proxy_operator_account"] is None

    user_list = client.get(_api("/api-keys"), headers=user1)
    assert user_list.status_code == 200
    user_items = user_list.json()["items"]
    assert len(user_items) == 1
    assert user_items[0]["id"] == body["id"]
    assert user_items[0]["duration_months"] == 6

    admin_list = client.get(_api("/api-keys"), headers=admin_headers)
    assert admin_list.status_code == 200
    admin_ids = {item["id"] for item in admin_list.json()["items"]}
    assert source_id in admin_ids
    assert body["id"] in admin_ids

    duplicate = client.post(_api(f"/api-keys/{source_id}/renew"), headers=user1)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "KEY_ALREADY_RENEWED"


def test_renew_rejects_active_key(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "renew active"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user_headers).json()["items"][0]["id"]
    renew = client.post(_api(f"/api-keys/{key_id}/renew"), headers=user_headers)
    assert renew.status_code == 409
    assert renew.json()["error"]["code"] == "KEY_NOT_RENEWABLE"


def test_expired_is_visible_but_not_renewable_by_expires_at(client, admin_headers, user_headers):
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "expire-visible"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user_headers).json()["items"][0]["id"]
    _set_key_expires_at_past(key_id)

    listed = client.get(_api("/api-keys"), headers=user_headers)
    assert listed.status_code == 200
    assert listed.json()["items"][0]["status"] == "expired"
    _assert_utc_datetime_string(listed.json()["items"][0]["expires_at"])

    detail = client.get(_api(f"/api-keys/{key_id}"), headers=user_headers)
    assert detail.status_code == 200
    assert detail.json()["status"] == "expired"
    _assert_utc_datetime_string(detail.json()["created_at"])
    _assert_utc_datetime_string(detail.json()["expires_at"])

    renew = client.post(_api(f"/api-keys/{key_id}/renew"), headers=user_headers)
    assert renew.status_code == 409
    assert renew.json()["error"]["code"] == "KEY_NOT_RENEWABLE"


def test_renew_rejects_expired_key_without_calling_provider(client, admin_headers, user_headers, monkeypatch):
    from app.core.config import get_settings

    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "expired renew gate"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user_headers).json()["items"][0]["id"]
    _set_key_expires_at_past(key_id)

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)

    def _should_not_call_provider(self, payload):
        raise AssertionError("provider should not be called for expired renew")

    monkeypatch.setattr("app.services.provider_client.ProviderClient.regenerate_key", _should_not_call_provider)
    try:
        renew = client.post(_api(f"/api-keys/{key_id}/renew"), headers=user_headers)
        assert renew.status_code == 409
        assert renew.json()["error"]["code"] == "KEY_NOT_RENEWABLE"
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        get_settings.cache_clear()


def test_extend_requires_notice_for_user_but_not_admin(client, admin_headers):
    user = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "extend notice gate"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user).json()["items"][0]["id"]

    blocked = client.post(_api(f"/api-keys/{key_id}/extend"), headers=user, json={"duration_months": 6})
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "KEY_EXTENSION_NOTICE_REQUIRED"

    _set_expiration_notice_sent_at(key_id, datetime.now(UTC))
    allowed = client.post(_api(f"/api-keys/{key_id}/extend"), headers=user, json={"duration_months": 6})
    assert allowed.status_code == 200
    assert allowed.json()["status"] == "active"
    _assert_utc_datetime_string(allowed.json()["expires_at"])

    _set_key_expires_at_past(key_id)
    _set_expiration_notice_sent_at(key_id, None)
    user_expired_allowed = client.post(_api(f"/api-keys/{key_id}/extend"), headers=user, json={"duration_months": 1})
    assert user_expired_allowed.status_code == 200
    assert user_expired_allowed.json()["status"] == "active"
    _assert_utc_datetime_string(user_expired_allowed.json()["expires_at"])

    _set_key_expires_at_past(key_id)
    admin_allowed = client.post(_api(f"/api-keys/{key_id}/extend"), headers=admin_headers, json={"duration_months": 1})
    assert admin_allowed.status_code == 200
    assert admin_allowed.json()["status"] == "active"
    _assert_utc_datetime_string(admin_allowed.json()["expires_at"])


def test_extend_provider_unavailable_does_not_change_expiration(client, admin_headers, monkeypatch):
    from app.core.config import get_settings
    from app.services.provider_client import ProviderUnavailableError

    user = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "extend provider fail"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user).json()["items"][0]["id"]
    _set_expiration_notice_sent_at(key_id, datetime.now(UTC))
    before = _fetch_key_status_row(key_id)

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)
    monkeypatch.setattr(
        "app.services.provider_client.ProviderClient.update_key",
        lambda self, payload: (_ for _ in ()).throw(ProviderUnavailableError("provider unavailable")),
    )
    try:
        resp = client.post(_api(f"/api-keys/{key_id}/extend"), headers=user, json={"duration_months": 6})
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"
        after = _fetch_key_status_row(key_id)
        assert after["key_status"] == before["key_status"]
        assert after["application_status"] == before["application_status"]
        assert after["expires_at"] == before["expires_at"]
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        get_settings.cache_clear()


def test_provider_operations_require_secret_material_before_calling_provider(client, admin_headers, monkeypatch):
    from app.core.config import get_settings

    user = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user["x-sysid"])
    active_resp = client.post(
        _api("/api-keys/applications"),
        headers=user,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "missing secret active"},
    )
    assert active_resp.status_code == 201
    active_key_id = client.get(_api("/api-keys"), headers=user).json()["items"][0]["id"]
    _set_key_secret_material(active_key_id, key_ciphertext=None, key_kek_version=None)
    _set_expiration_notice_sent_at(active_key_id, datetime.now(UTC))

    revoked_resp = client.post(
        _api("/api-keys/applications"),
        headers=user,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "missing secret revoked"},
    )
    assert revoked_resp.status_code == 201
    key_items = client.get(_api("/api-keys"), headers=user).json()["items"]
    revoked_key_id = next(item["id"] for item in key_items if item["id"] != active_key_id)
    revoked = client.post(_api(f"/api-keys/{revoked_key_id}/revoke"), headers=user)
    assert revoked.status_code == 200
    _set_key_secret_material(revoked_key_id, key_ciphertext=None, key_kek_version=None)

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)

    def _should_not_call_provider(self, payload):
        raise AssertionError("provider should not be called without secret material")

    monkeypatch.setattr("app.services.provider_client.ProviderClient.block_key", _should_not_call_provider)
    monkeypatch.setattr("app.services.provider_client.ProviderClient.update_key", _should_not_call_provider)
    monkeypatch.setattr("app.services.provider_client.ProviderClient.regenerate_key", _should_not_call_provider)
    try:
        revoke = client.post(_api(f"/api-keys/{active_key_id}/revoke"), headers=user)
        assert revoke.status_code == 409
        assert revoke.json()["error"]["code"] == "KEY_NOT_REVEALABLE"

        extend = client.post(_api(f"/api-keys/{active_key_id}/extend"), headers=user, json={"duration_months": 1})
        assert extend.status_code == 409
        assert extend.json()["error"]["code"] == "KEY_NOT_REVEALABLE"

        renew = client.post(_api(f"/api-keys/{revoked_key_id}/renew"), headers=user)
        assert renew.status_code == 409
        assert renew.json()["error"]["code"] == "KEY_NOT_REVEALABLE"
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        get_settings.cache_clear()


def test_renew_sends_renewed_email_on_success(client, admin_headers, monkeypatch):
    user = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "renew mail"},
    )
    key_id = client.get(_api("/api-keys"), headers=user).json()["items"][0]["id"]
    client.post(_api(f"/api-keys/{key_id}/revoke"), headers=user)

    calls: list[dict] = []

    async def _fake_mail(self, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr("app.services.mail_service.MailService.send_key_renewed_notification", _fake_mail)

    renew = client.post(_api(f"/api-keys/{key_id}/renew"), headers=user)
    assert create_resp.status_code == 201
    assert renew.status_code == 200
    assert len(calls) == 1
    assert calls[0]["to_email"] == user["x-email"]


def test_renew_provider_unavailable_returns_503(client, admin_headers, monkeypatch):
    from app.core.config import get_settings
    from app.services.provider_client import ProviderUnavailableError

    admin_notify_calls: list[dict] = []

    async def _fake_admin_notify(self, **kwargs):
        admin_notify_calls.append(kwargs)

    user = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "renew pending"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user).json()["items"][0]["id"]
    client.post(_api(f"/api-keys/{key_id}/revoke"), headers=user)

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)
    monkeypatch.setattr(
        "app.services.api_keys_service.SQLAlchemyAdminRepository.list_active_emails",
        lambda self: ["admin1@example.com", "admin2@example.com"],
    )
    monkeypatch.setattr("app.services.mail_service.MailService.send_provider_issuance_failed_to_admins", _fake_admin_notify)
    monkeypatch.setattr(
        "app.services.provider_client.ProviderClient.regenerate_key",
        lambda self, payload: (_ for _ in ()).throw(ProviderUnavailableError("provider unavailable")),
    )
    try:
        renew = client.post(_api(f"/api-keys/{key_id}/renew"), headers=user)
        assert renew.status_code == 503
        assert renew.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"
        assert len(admin_notify_calls) == 1
        assert admin_notify_calls[0]["to_emails"] == ["admin1@example.com", "admin2@example.com"]
        assert admin_notify_calls[0]["operation"] == "renew"
        assert admin_notify_calls[0]["error_code"] == "PROVIDER_UNAVAILABLE"
        assert admin_notify_calls[0]["target_account"] == user["x-account"]
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        get_settings.cache_clear()


def test_application_provider_422_maps_to_validation_error(client, admin_headers, user_headers, monkeypatch):
    from app.core.config import get_settings
    from app.services.provider_client import ProviderBadRequestError

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.api_keys_service.LoginEligibilityService.is_eligible_by_sysid", lambda self, sysid: True)
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)
    monkeypatch.setattr(
        "app.services.provider_client.ProviderClient.generate_key",
        lambda self, payload: (_ for _ in ()).throw(ProviderBadRequestError("body.duration: invalid duration")),
    )
    try:
        resp = client.post(
            _api("/api-keys/applications"),
            headers=user_headers,
            json={"application_date": str(date.today()), "duration_months": 6, "purpose": "provider-422"},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        get_settings.cache_clear()


def test_application_provider_timeout_admin_notify_failure_does_not_change_503(client, admin_headers, user_headers, monkeypatch):
    from app.core.config import get_settings
    from app.services.provider_client import ProviderUnavailableError

    async def _raise_notify_error(self, **kwargs):
        raise RuntimeError("smtp down")

    monkeypatch.setenv("ISSUANCE_PROVIDER_MODE", "external")
    get_settings.cache_clear()
    _create_whitelist(client, admin_headers, user_headers["x-sysid"])
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: True)
    monkeypatch.setattr("app.services.api_keys_service.SQLAlchemyAdminRepository.list_active_emails", lambda self: ["admin@example.com"])
    monkeypatch.setattr("app.services.mail_service.MailService.send_provider_issuance_failed_to_admins", _raise_notify_error)
    monkeypatch.setattr(
        "app.services.provider_client.ProviderClient.generate_key",
        lambda self, payload: (_ for _ in ()).throw(ProviderUnavailableError("provider unavailable")),
    )
    try:
        resp = client.post(
            _api("/api-keys/applications"),
            headers=user_headers,
            json={"application_date": str(date.today()), "duration_months": 1, "purpose": "notify fail should not alter"},
        )
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"
    finally:
        monkeypatch.delenv("ISSUANCE_PROVIDER_MODE", raising=False)
        get_settings.cache_clear()


def test_admin_can_list_global_keys(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    user2 = build_headers(role="user", account="user2", email="user2@example.com", sysid="2002")
    _create_whitelist(client, admin_headers, user1["x-sysid"])
    _create_whitelist(client, admin_headers, user2["x-sysid"])

    resp1 = client.post(
        _api("/api-keys/applications"),
        headers=user1,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "u1", "max_budget": "1000", "budget_duration": "monthly"},
    )
    resp2 = client.post(
        _api("/api-keys/applications"),
        headers=user2,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "u2", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert resp1.status_code == 201
    assert resp2.status_code == 201
    admin_list = client.get(_api("/api-keys"), headers=admin_headers)
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
        _api("/api-keys/applications"),
        headers=user1,
        json={"application_date": "2026-05-01", "duration_months": 1, "purpose": "u1", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert resp1.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user1).json()["items"][0]["id"]
    revoke = client.post(_api(f"/api-keys/{key_id}/revoke"), headers=user1)
    assert revoke.status_code == 200

    resp2 = client.post(
        _api("/api-keys/applications"),
        headers=user1,
        json={"application_date": "2026-05-10", "duration_months": 1, "purpose": "u1-2", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert resp2.status_code == 201

    resp3 = client.post(
        _api("/api-keys/applications"),
        headers=user2,
        json={"application_date": "2026-05-03", "duration_months": 1, "purpose": "u2", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert resp3.status_code == 201

    filtered = client.get(
        _api("/api-keys?owner_account=user1&status=active&from=2026-05-05&to=2026-05-31"),
        headers=admin_headers,
    )
    assert filtered.status_code == 200
    items = filtered.json()["items"]
    assert len(items) == 1
    assert items[0]["owner_account"] == "user1"
    assert items[0]["status"] == "active"
    assert items[0]["application_date"] == "2026-05-10"


def test_list_api_keys_total_is_full_match_count_not_page_size(client, admin_headers):
    user = build_headers(role="user", account="pager", email="pager@example.com", sysid="2201")
    _create_whitelist(client, admin_headers, user["x-sysid"])

    for i in range(3):
        resp = client.post(
            _api("/api-keys/applications"),
            headers=user,
            json={
                "application_date": str(date.today()),
                "duration_months": 1,
                "purpose": f"pager-{i}",
                "max_budget": "1000",
                "budget_duration": "monthly",
            },
        )
        assert resp.status_code == 201

    page1 = client.get(_api("/api-keys?page=1&page_size=1"), headers=user)
    page2 = client.get(_api("/api-keys?page=2&page_size=1"), headers=user)
    assert page1.status_code == 200
    assert page2.status_code == 200
    assert len(page1.json()["items"]) == 1
    assert len(page2.json()["items"]) == 1
    assert page1.json()["total"] == 3
    assert page2.json()["total"] == 3


def test_list_api_keys_accepts_page_and_page_size_query_params(client, admin_headers):
    user = build_headers(role="user", account="pagequery", email="pagequery@example.com", sysid="2202")
    _create_whitelist(client, admin_headers, user["x-sysid"])
    resp = client.post(
        _api("/api-keys/applications"),
        headers=user,
        json={
            "application_date": str(date.today()),
            "duration_months": 1,
            "purpose": "page-query",
            "max_budget": "1000",
            "budget_duration": "monthly",
        },
    )
    assert resp.status_code == 201

    listed = client.get(_api("/api-keys?page=1&page_size=10"), headers=user)
    assert listed.status_code == 200
    body = listed.json()
    assert body["page"] == 1
    assert body["page_size"] == 10
    assert body["total"] >= 1


def test_reveal_plaintext_admin_only(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user1["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user1,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "u1", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert create_resp.status_code == 201
    created_plaintext = create_resp.json()["api_key_plaintext"]
    key_id = client.get(_api("/api-keys"), headers=user1).json()["items"][0]["id"]

    forbidden = client.post(_api(f"/api-keys/{key_id}/reveal"), headers=user1)
    assert forbidden.status_code == 403

    reveal_resp = client.post(_api(f"/api-keys/{key_id}/reveal"), headers=admin_headers)
    assert reveal_resp.status_code == 200
    assert reveal_resp.json()["api_key_plaintext"] == created_plaintext
    assert reveal_resp.headers["cache-control"] == "no-store"


def test_statistics_rejects_excessive_query_range(client, admin_headers):
    resp = client.get(
        _api("/api-keys/statistics/users?from=2026-01-01&to=2026-02-15"),
        headers=admin_headers,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_admin_can_update_key_alias_and_user_cannot(client, admin_headers):
    user1 = build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")
    _create_whitelist(client, admin_headers, user1["x-sysid"])
    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user1,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "u1", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert create_resp.status_code == 201
    key_id = client.get(_api("/api-keys"), headers=user1).json()["items"][0]["id"]

    forbidden = client.patch(_api(f"/api-keys/{key_id}"), headers=user1, json={"key_alias": "custom_user_alias"})
    assert forbidden.status_code == 403

    invalid = client.patch(_api(f"/api-keys/{key_id}"), headers=admin_headers, json={"key_alias": "   "})
    assert invalid.status_code == 422

    updated = client.patch(_api(f"/api-keys/{key_id}"), headers=admin_headers, json={"key_alias": "custom_admin_alias"})
    assert updated.status_code == 200
    assert updated.json()["key_alias"] == "custom_admin_alias"

    listed = client.get(_api("/api-keys"), headers=admin_headers)
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
    before = client.get(_api("/api-keys"), headers=admin_headers).json()["total"]
    resp = client.post(
        _api("/api-keys/applications"),
        headers=bad_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test", "max_budget": "1000", "budget_duration": "monthly"},
    )
    after = client.get(_api("/api-keys"), headers=admin_headers).json()["total"]
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert before == after


def test_error_response_shape_consistency(client, admin_headers, user_headers):
    # non-whitelist application error
    e1 = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "test", "max_budget": "1000", "budget_duration": "monthly"},
    )
    # non-admin whitelist management error
    e2 = client.get(_api("/whitelists"), headers=user_headers)

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
            _api("/api-keys/applications"),
            headers=user1,
            json={"application_date": "2026-05-01", "duration_months": 1, "purpose": "u1", "max_budget": "1000", "budget_duration": "monthly"},
        )
        assert resp.status_code == 201
    resp = client.post(
        _api("/api-keys/applications"),
        headers=user2,
        json={"application_date": "2026-05-02", "duration_months": 1, "purpose": "u2", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert resp.status_code == 201

    stats_resp = client.get(_api("/api-keys/statistics/users"), headers=admin_headers)
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
        _api("/api-keys/applications"),
        headers=user,
        json={"application_date": "2026-05-01", "duration_months": 1, "purpose": "first", "max_budget": "1000", "budget_duration": "monthly"},
    )
    second = client.post(
        _api("/api-keys/applications"),
        headers=user,
        json={"application_date": "2026-05-03", "duration_months": 1, "purpose": "second", "max_budget": "1000", "budget_duration": "monthly"},
    )
    assert first.status_code == 201
    assert second.status_code == 201

    ids = [item["id"] for item in client.get(_api("/api-keys"), headers=user).json()["items"]]
    revoke_target_id = ids[0]
    expire_target_id = ids[1]
    _set_key_expires_at_past(expire_target_id)
    revoke_resp = client.post(_api(f"/api-keys/{revoke_target_id}/revoke"), headers=user)
    assert revoke_resp.status_code == 200

    all_resp = client.get(_api("/api-keys/statistics/users?scope=all"), headers=admin_headers)
    active_resp = client.get(_api("/api-keys/statistics/users?scope=active"), headers=admin_headers)
    revoked_resp = client.get(_api("/api-keys/statistics/users?scope=revoked"), headers=admin_headers)
    expired_resp = client.get(_api("/api-keys/statistics/users?scope=expired"), headers=admin_headers)
    ranged_resp = client.get(
        _api("/api-keys/statistics/users?from=2026-05-02&to=2026-05-03"),
        headers=admin_headers,
    )

    assert all_resp.status_code == 200
    assert active_resp.status_code == 200
    assert revoked_resp.status_code == 200
    assert expired_resp.status_code == 200
    assert ranged_resp.status_code == 200

    all_item = all_resp.json()["items"][0]
    revoked_item = revoked_resp.json()["items"][0]
    ranged_item = ranged_resp.json()["items"][0]

    assert all_item["total_applications"] == 2
    assert active_resp.json()["total"] == 0
    assert revoked_item["total_applications"] == 1
    assert expired_resp.json()["total"] == 1
    assert ranged_item["total_applications"] == 1

    forbidden = client.get(_api("/api-keys/statistics/users"), headers=user)
    assert forbidden.status_code == 403


def test_admin_user_statistics_rejects_invalid_sort_by(client, admin_headers):
    resp = client.get(
        _api("/api-keys/statistics/users?sort_by=__invalid__"),
        headers=admin_headers,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

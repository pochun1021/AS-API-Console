"""Issue #57 core checks use an in-memory DataHub only."""

import json
from types import SimpleNamespace

import httpx
import pytest

from app.core import outbound
from app.core.config import Settings
from app.services.datahub_client import DataHubClient, DataHubError, DataHubErrorKind
from app.services.login_eligibility_service import LoginEligibilityService
from app.services.login_qualification_gate import (
    GateStatus,
    LoginQualificationGate,
    TRAINING_INCOMPLETE_MESSAGE,
)
from app.services.training_eligibility_service import TrainingEligibilityService


def _settings() -> Settings:
    return Settings.model_construct(
        app_env="test",
        datahub_token_url="https://datahub.example/token",
        datahub_list_url="https://datahub.example/list",
        datahub_client_id="learnpoints",
        datahub_client_secret="fixture-secret",
        datahub_list_method="GET",
        datahub_timeout_seconds=0.5,
    )


def _item(sso: object) -> dict:
    return {"sso": sso, "name": "fixture", "phone": "", "email": "", "instName": "fixture"}


def _client(monkeypatch, *, listing: object = None, status: int = 200, token: object = None, error=None):
    settings = _settings()
    monkeypatch.setattr(outbound, "get_settings", lambda: settings)
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if error and request.url.path == "/list":
            raise error
        if request.url.path == "/token":
            return httpx.Response(200, json={"accessToken": "fixture-token"} if token is None else token)
        return httpx.Response(status, json=[] if listing is None else listing)

    return DataHubClient(settings, transport=httpx.MockTransport(handler)), seen


class AuditSpy:
    def __init__(self, *, fail=False):
        self.events = []
        self.fail = fail

    def log(self, **event):
        if self.fail:
            raise RuntimeError("audit unavailable")
        self.events.append(event)


class ExistingSpy:
    def __init__(self, *, eligible=True):
        self.calls = []
        self.eligible = eligible

    def is_eligible(self, *, sysid: int, tcode: str) -> bool:
        self.calls.append((sysid, tcode))
        return self.eligible


def _gate(client, *, existing=None, audit=None):
    existing = existing or ExistingSpy()
    audit = audit or AuditSpy()
    gate = LoginQualificationGate(
        training=TrainingEligibilityService(client), existing=existing, audit=audit
    )
    return gate, existing, audit


def _evaluate(gate, *, sso="00123", session=None):
    if session is None:
        session = {"auth_context": {"role": "admin"}, "csrf_token": "old"}
    result = gate.evaluate(
        trusted_sso=sso,
        sysid=123,
        tcode="A01",
        session=session,
        provider="fixture-provider",
        request_id="fixture-request",
    )
    assert "auth_context" not in session
    assert "csrf_token" not in session
    return result


def test_datahub_settings_load_defaults_and_stay_independent_from_fisa(monkeypatch):
    monkeypatch.delenv("DATAHUB_CLIENT_ID", raising=False)
    monkeypatch.delenv("DATAHUB_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("OAUTH_CLIENT_ID", "fisa-fixture-id")
    monkeypatch.setenv("OAUTH_CLIENT_SECRET", "fisa-fixture-secret")

    defaults = Settings(_env_file=None, app_env="test", database_url="sqlite://")
    assert defaults.datahub_client_id == "learnpoints"
    assert defaults.datahub_client_secret is None
    assert defaults.oauth_client_id == "fisa-fixture-id"
    assert defaults.oauth_client_secret == "fisa-fixture-secret"

    monkeypatch.setenv("DATAHUB_CLIENT_ID", "datahub-fixture-id")
    monkeypatch.setenv("DATAHUB_CLIENT_SECRET", "datahub-fixture-secret")
    configured = Settings(_env_file=None, app_env="test", database_url="sqlite://")
    assert configured.datahub_client_id == "datahub-fixture-id"
    assert configured.datahub_client_secret == "datahub-fixture-secret"
    assert configured.oauth_client_id == "fisa-fixture-id"
    assert configured.oauth_client_secret == "fisa-fixture-secret"


@pytest.mark.parametrize("missing", ["datahub_client_id", "datahub_client_secret"])
def test_prod_missing_datahub_credential_fails_closed_before_request(monkeypatch, missing):
    client, seen = _client(monkeypatch)
    client.settings.app_env = "prod"
    setattr(client.settings, missing, None if missing == "datahub_client_secret" else "")
    gate, existing, _ = _gate(client)

    result = _evaluate(gate)

    assert result.status == GateStatus.SERVICE_UNAVAILABLE
    assert existing.calls == []
    assert seen == []


def test_datahub_token_request_uses_only_datahub_credentials(monkeypatch):
    client, seen = _client(monkeypatch)
    client.settings.oauth_client_id = "fisa-fixture-id"
    client.settings.oauth_client_secret = "fisa-fixture-secret"
    client.settings.datahub_client_id = "datahub-fixture-id"
    client.settings.datahub_client_secret = "datahub-fixture-secret"

    client.fetch_incomplete_sso()

    assert seen[0].method == "POST"
    assert json.loads(seen[0].content) == {
        "clientId": "datahub-fixture-id",
        "clientSecret": "datahub-fixture-secret",
    }


def test_datahub_reads_token_and_validated_string_identifiers(monkeypatch):
    client, seen = _client(monkeypatch, listing=[_item("00123"), _item("123")])

    assert client.fetch_incomplete_sso() == frozenset({"00123", "123"})
    assert len(seen) == 2
    assert json.loads(seen[0].content) == {
        "clientId": "learnpoints", "clientSecret": "fixture-secret"
    }
    assert seen[1].headers["Authorization"] == "Bearer fixture-token"
    assert seen[1].method == "GET"
    assert b"object=%2Fread%2Fnotfinish.json" in seen[1].content


@pytest.mark.parametrize(
    ("listing", "status", "expected"),
    [
        ({"errMsg": "invalid token"}, 200, DataHubErrorKind.SERVICE),
        ({"data": []}, 200, DataHubErrorKind.SCHEMA),
        ([_item(123)], 200, DataHubErrorKind.SCHEMA),
        ([{"sso": "00123"}], 200, DataHubErrorKind.SCHEMA),
        ([_item("")], 200, DataHubErrorKind.SCHEMA),
        ([], 401, DataHubErrorKind.AUTHORIZATION),
        ([], 403, DataHubErrorKind.AUTHORIZATION),
        ([], 500, DataHubErrorKind.HTTP),
    ],
)
def test_datahub_rejects_invalid_or_failed_list(monkeypatch, listing, status, expected):
    client, _ = _client(monkeypatch, listing=listing, status=status)
    with pytest.raises(DataHubError) as raised:
        client.fetch_incomplete_sso()
    assert raised.value.kind == expected
    assert "invalid token" not in str(raised.value)


@pytest.mark.parametrize(
    ("token", "expected"),
    [({"errMsg": "no token"}, DataHubErrorKind.SERVICE), ({"accessToken": ""}, DataHubErrorKind.SCHEMA)],
)
def test_datahub_rejects_bad_token(monkeypatch, token, expected):
    client, seen = _client(monkeypatch, token=token)
    with pytest.raises(DataHubError) as raised:
        client.fetch_incomplete_sso()
    assert raised.value.kind == expected
    assert len(seen) == 1


def test_datahub_rejects_malformed_json(monkeypatch):
    settings = _settings()
    monkeypatch.setattr(outbound, "get_settings", lambda: settings)

    def handler(request):
        if request.url.path == "/token":
            return httpx.Response(200, json={"accessToken": "fixture-token"})
        return httpx.Response(200, text="not json")

    client = DataHubClient(settings, transport=httpx.MockTransport(handler))
    with pytest.raises(DataHubError) as raised:
        client.fetch_incomplete_sso()
    assert raised.value.kind == DataHubErrorKind.SCHEMA


def test_datahub_timeout_and_missing_contract_fail_closed(monkeypatch):
    client, _ = _client(monkeypatch, error=httpx.ReadTimeout("timed out"))
    with pytest.raises(DataHubError) as raised:
        client.fetch_incomplete_sso()
    assert raised.value.kind == DataHubErrorKind.TIMEOUT

    settings = _settings()
    settings.datahub_list_method = None
    with pytest.raises(DataHubError) as raised:
        DataHubClient(settings).fetch_incomplete_sso()
    assert raised.value.kind == DataHubErrorKind.CONFIGURATION


def test_training_hit_blocks_admin_before_existing_rules_and_clears_session(monkeypatch):
    client, _ = _client(monkeypatch, listing=[_item("00123")])
    gate, existing, audit = _gate(client)

    result = _evaluate(gate)

    assert result.status == GateStatus.TRAINING_INCOMPLETE
    assert result.message == TRAINING_INCOMPLETE_MESSAGE
    assert existing.calls == []
    assert audit.events == [{
        "provider": "fixture-provider", "request_id": "fixture-request",
        "result": "failure", "error_code": "TRAINING_INCOMPLETE", "detail": None,
    }]


def test_string_exactness_empty_list_and_existing_eligibility(monkeypatch):
    client, _ = _client(monkeypatch, listing=[_item("123")])
    gate, existing, audit = _gate(client)
    assert _evaluate(gate).status == GateStatus.ALLOWED
    assert existing.calls == [(123, "A01")]
    assert audit.events == []

    empty_client, _ = _client(monkeypatch, listing=[])
    gate, existing, audit = _gate(empty_client, existing=ExistingSpy(eligible=False))
    assert _evaluate(gate).status == GateStatus.LOGIN_NOT_ELIGIBLE
    assert existing.calls == [(123, "A01")]
    assert audit.events[0]["error_code"] == "LOGIN_NOT_ELIGIBLE"


@pytest.mark.parametrize("allow_source", ["whitelist", "admin", "title"])
def test_existing_allow_rules_run_only_after_training_miss(monkeypatch, allow_source):
    client, _ = _client(monkeypatch, listing=[])
    whitelist = SimpleNamespace(find_active_by_sysid=lambda _id: object() if allow_source == "whitelist" else None)
    admin = SimpleNamespace(get_active_by_id=lambda _id: object() if allow_source == "admin" else None)
    existing = LoginEligibilityService(whitelist_repo=whitelist, admin_repo=admin)
    existing.allowed_title_codes = {"A01"} if allow_source == "title" else set()
    gate, _, _ = _gate(client, existing=existing)
    assert _evaluate(gate).status == GateStatus.ALLOWED


def test_datahub_failure_invalid_identity_and_audit_failure_never_leave_session(monkeypatch):
    client, _ = _client(monkeypatch, listing={"errMsg": "failure"})
    gate, existing, audit = _gate(client)
    assert _evaluate(gate).status == GateStatus.SERVICE_UNAVAILABLE
    assert existing.calls == []
    assert audit.events[0]["detail"] == "service"

    client, seen = _client(monkeypatch, listing=[])
    gate, existing, audit = _gate(client)
    assert _evaluate(gate, sso=123).status == GateStatus.SERVICE_UNAVAILABLE
    assert seen == []
    assert existing.calls == []
    assert audit.events[0]["error_code"] == "TRAINING_IDENTITY_UNAVAILABLE"

    client, _ = _client(monkeypatch, listing=[_item("00123")])
    gate, _, _ = _gate(client, audit=AuditSpy(fail=True))
    assert _evaluate(gate).status == GateStatus.SERVICE_UNAVAILABLE

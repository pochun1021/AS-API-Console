from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from app.core.config import get_settings
from db.models.api_keys import ApiKey
from db.models.applications import ApiKeyApplication
from tests.conftest import api_path, build_headers


@pytest.fixture(autouse=True)
def _enable_header_auth_for_statistics_tests(monkeypatch):
    monkeypatch.setenv("ALLOW_HEADER_AUTH", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _seed_application(session, *, account, department, day, status="active", expires_at=None, with_key=True):
    app_id = str(uuid4())
    key_id = str(uuid4())
    session.add(ApiKeyApplication(
        id=app_id,
        account=account,
        name=account,
        email=f"{account}@example.com",
        department=department,
        application_date=day,
        duration_days=30,
        original_duration_days=30,
        purpose="statistics regression",
        status="active",  # Deliberately disagree with the key for revoked rows.
        issued_at=datetime(2026, 5, 1, tzinfo=UTC),
        expires_at=expires_at or datetime(2027, 5, 1, tzinfo=UTC),
        sysid=9000,
    ))
    if with_key:
        session.add(ApiKey(
            id=key_id,
            application_id=app_id,
            key_hash=f"hash-{key_id}",
            masked_key="AS-****",
            status=status,
        ))
    return key_id


def test_existing_statistics_counts_joined_applications_once_and_uses_key_status(
    client, admin_headers, testing_session_local
):
    with testing_session_local() as session:
        old_id = _seed_application(session, account="alice", department="D1", day=date(2026, 5, 1), status="revoked")
        new_id = _seed_application(session, account="alice", department="D1", day=date(2026, 5, 3))
        session.flush()
        session.get(ApiKey, old_id).renewed_to_key_id = new_id
        _seed_application(
            session, account="alice", department="D1", day=date(2026, 5, 3),
            expires_at=datetime(2026, 5, 4, tzinfo=UTC),
        )
        _seed_application(session, account="alice", department="D1", day=date(2026, 5, 3), with_key=False)
        session.commit()

    base = api_path("/api-keys/statistics/users")
    all_response = client.get(base, headers=admin_headers)
    assert all_response.status_code == 200
    assert all_response.json()["total"] == 1
    item = all_response.json()["items"][0]
    assert (item["total_applications"], item["active_count"], item["revoked_count"], item["expired_count"]) == (3, 1, 1, 1)
    assert client.get(f"{base}?scope=revoked", headers=admin_headers).json()["items"][0]["total_applications"] == 1
    ranged = client.get(f"{base}?from=2026-05-03&to=2026-05-03", headers=admin_headers)
    assert ranged.json()["items"][0]["total_applications"] == 2


def test_chart_aggregates_full_dataset_before_topn_and_groups_departments(
    client, admin_headers, testing_session_local
):
    with testing_session_local() as session:
        for index in range(22):
            _seed_application(
                session, account=f"user{index:02d}",
                department="SHARED" if index < 6 else f"D{index:02d}",
                day=date(2026, 5, 1),
            )
        _seed_application(session, account="user00", department="SHARED", day=date(2026, 5, 2), status="revoked")
        _seed_application(session, account="user01", department="SHARED", day=date(2026, 5, 3), expires_at=datetime(2026, 5, 4, tzinfo=UTC))
        _seed_application(session, account="orphan", department="SHARED", day=date(2026, 5, 1), with_key=False)
        session.commit()

    base = api_path("/api-keys/statistics/chart")
    account = client.get(f"{base}?x_axis=account&top_n=5", headers=admin_headers)
    assert account.status_code == 200
    body = account.json()
    assert body["group_count"] == 22
    assert body["total_value"] == 24
    assert body["displayed_value"] == 7
    assert len(body["items"]) == 5
    assert body["items"][0] == {"label": "user00", "value": 2}
    for top_n in (10, 20):
        expanded = client.get(f"{base}?x_axis=account&top_n={top_n}", headers=admin_headers).json()
        assert len(expanded["items"]) == top_n
        assert expanded["group_count"] == 22
        assert expanded["total_value"] == 24
        assert expanded["displayed_value"] == top_n + 2

    department = client.get(f"{base}?x_axis=department&top_n=5", headers=admin_headers)
    assert department.status_code == 200
    grouped = department.json()
    assert grouped["group_count"] == 17
    assert grouped["total_value"] == 24
    assert grouped["displayed_value"] == 12
    assert grouped["items"][0] == {"label": "SHARED", "value": 8}

    revoked = client.get(f"{base}?x_axis=department&y_axis=revoked_count&scope=all", headers=admin_headers)
    assert revoked.json()["total_value"] == 1
    active = client.get(f"{base}?y_axis=active_count", headers=admin_headers)
    assert active.json()["total_value"] == 22
    revoked_scope = client.get(f"{base}?scope=revoked", headers=admin_headers).json()
    assert (revoked_scope["total_value"], revoked_scope["group_count"]) == (1, 1)
    expired = client.get(f"{base}?x_axis=department&y_axis=expired_count&from=2026-05-03&to=2026-05-03", headers=admin_headers)
    assert expired.json()["total_value"] == 1
    ranged = client.get(f"{base}?from=2026-05-02&to=2026-05-03", headers=admin_headers)
    assert ranged.json()["total_value"] == 2
    filtered = client.get(f"{base}?x_axis=department&owner_department=shared&scope=active", headers=admin_headers)
    assert filtered.json()["items"] == [{"label": "SHARED", "value": 6}]
    empty = client.get(f"{base}?owner_account=missing", headers=admin_headers).json()
    assert (empty["items"], empty["total_value"], empty["displayed_value"], empty["group_count"]) == ([], 0, 0, 0)


def test_chart_rejects_invalid_options_and_non_admin(client, admin_headers):
    base = api_path("/api-keys/statistics/chart")
    for query in ("x_axis=invalid", "y_axis=invalid", "top_n=3", "scope=invalid", "from=2026-05-03&to=2026-05-01"):
        assert client.get(f"{base}?{query}", headers=admin_headers).status_code == 422
    user = build_headers(role="user", account="user", email="user@example.com", sysid=2)
    assert client.get(base, headers=user).status_code == 403

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from app.core.config import get_settings
from app.services.crypto_service import CryptoService
from db.models.api_keys import ApiKey
from db.models.applications import ApiKeyApplication
from tests.conftest import api_path, build_headers


@pytest.fixture(autouse=True)
def _enable_header_auth_for_statistics_tests(monkeypatch):
    monkeypatch.setenv("ALLOW_HEADER_AUTH", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _seed_application(
    session, *, account, department, day, status="active", expires_at=None, with_key=True,
    name=None, email=None,
):
    app_id = str(uuid4())
    key_id = str(uuid4())
    session.add(ApiKeyApplication(
        id=app_id,
        account=account,
        name=name or account,
        email=email or f"{account}@example.com",
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


def test_department_chart_uses_same_owner_department_as_table(
    client, admin_headers, testing_session_local
):
    with testing_session_local() as session:
        _seed_application(session, account="alice", department="IT", day=date(2026, 5, 1))
        _seed_application(session, account="alice", department="R&D", day=date(2026, 5, 2))
        _seed_application(session, account="bob", department="IT", day=date(2026, 5, 3))
        session.commit()

    users = client.get(api_path("/api-keys/statistics/users"), headers=admin_headers)
    assert users.status_code == 200
    departments = client.get(api_path("/api-keys/statistics/departments"), headers=admin_headers)
    assert departments.status_code == 200
    assert departments.json() == {"items": ["IT", "R&D"]}
    assert {
        row["owner_account"]: (row["owner_department"], row["total_applications"])
        for row in users.json()["items"]
    } == {"alice": ("R&D", 2), "bob": ("IT", 1)}

    chart = client.get(api_path("/api-keys/statistics/chart?x_axis=department"), headers=admin_headers)
    assert chart.status_code == 200
    assert chart.json()["items"] == [{"label": "R&D", "value": 2}, {"label": "IT", "value": 1}]
    assert (
        chart.json()["total_value"],
        chart.json()["displayed_value"],
        chart.json()["group_count"],
    ) == (3, 3, 2)

    filtered_users = client.get(
        api_path("/api-keys/statistics/users?owner_department=R%26D"), headers=admin_headers
    )
    assert filtered_users.status_code == 200
    assert filtered_users.json()["items"][0]["total_applications"] == 2
    assert filtered_users.json()["total"] == 1

    filtered_chart = client.get(
        api_path("/api-keys/statistics/chart?x_axis=department&owner_department=R%26D"),
        headers=admin_headers,
    )
    assert filtered_chart.status_code == 200
    assert filtered_chart.json()["items"] == [{"label": "R&D", "value": 2}]
    assert filtered_chart.json()["total_value"] == 2


def test_extend_moves_application_date_without_creating_another_statistic(
    client, admin_headers, testing_session_local
):
    today = date.today()
    with testing_session_local() as session:
        key_id = _seed_application(
            session, account="alice", department="IT", day=date(2026, 5, 1),
            expires_at=datetime(2099, 1, 1, tzinfo=UTC),
        )
        session.flush()
        key = session.get(ApiKey, key_id)
        settings = get_settings()
        key.key_ciphertext = CryptoService(settings.api_key_encryption_secret).encrypt("AS-" + "a" * 30)
        key.key_kek_version = settings.api_key_kek_version
        session.commit()

    users_url = api_path("/api-keys/statistics/users")
    chart_url = api_path("/api-keys/statistics/chart")
    date_query = f"from={today}&to={today}"
    assert client.get(f"{users_url}?{date_query}", headers=admin_headers).json()["total"] == 0
    assert client.get(f"{chart_url}?{date_query}", headers=admin_headers).json()["total_value"] == 0

    extended = client.post(api_path(f"/api-keys/{key_id}/extend"), headers=admin_headers, json={})
    assert extended.status_code == 200
    assert extended.json()["id"] == key_id

    users = client.get(f"{users_url}?{date_query}", headers=admin_headers).json()
    assert users["total"] == 1
    assert (users["items"][0]["total_applications"], users["items"][0]["active_count"]) == (1, 1)
    chart = client.get(f"{chart_url}?{date_query}", headers=admin_headers).json()
    assert chart["items"] == [{"label": "alice", "value": 1}]
    assert (chart["total_value"], chart["displayed_value"], chart["group_count"]) == (1, 1, 1)
    assert client.get(users_url, headers=admin_headers).json()["items"][0]["total_applications"] == 1


def test_owner_filters_keep_table_and_chart_counts_on_matching_owners(
    client, admin_headers, testing_session_local
):
    with testing_session_local() as session:
        for department in ("IT", "R&D"):
            _seed_application(
                session, account="alice", name="Alice Chen", email="alice@sample.test",
                department=department, day=date(2026, 5, 1),
            )
        _seed_application(
            session, account="bob", name="Bob Lin", email="bob@sample.test",
            department="IT", day=date(2026, 5, 1),
        )
        _seed_application(
            session, account="carol", name="Carol Wu", email="carol@sample.test",
            department="R&D", day=date(2026, 5, 1),
        )
        session.commit()

    users_url = api_path("/api-keys/statistics/users")
    chart_url = api_path("/api-keys/statistics/chart")
    for query in ("owner_account=ALI", "owner_name=ALICE", "owner_email=ALICE%40SAMPLE.TEST"):
        users = client.get(f"{users_url}?{query}", headers=admin_headers).json()
        chart = client.get(f"{chart_url}?{query}", headers=admin_headers).json()
        assert [(row["owner_account"], row["total_applications"]) for row in users["items"]] == [("alice", 2)]
        assert chart["items"] == [{"label": "alice", "value": 2}]
        assert (chart["total_value"], chart["group_count"]) == (2, 1)

    department_query = "owner_department=R%26D"
    users = client.get(f"{users_url}?{department_query}", headers=admin_headers).json()
    chart = client.get(f"{chart_url}?x_axis=department&{department_query}", headers=admin_headers).json()
    assert [(row["owner_account"], row["total_applications"]) for row in users["items"]] == [
        ("alice", 2), ("carol", 1),
    ]
    assert chart["items"] == [{"label": "R&D", "value": 3}]
    assert (chart["total_value"], chart["displayed_value"], chart["group_count"]) == (3, 3, 1)


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
    assert client.get(api_path("/api-keys/statistics/departments"), headers=user).status_code == 403

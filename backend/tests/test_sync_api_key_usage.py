from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from tests.conftest import api_path as _api


def _fetch_usage_snapshot_rows(key_id: str) -> list[dict]:
    settings = get_settings()
    db_url = settings.test_database_url or settings.database_url
    engine = create_engine(db_url, future=True)
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT api_key_id, spend, prompt_tokens, completion_tokens, total_tokens, budget_reset_at, synced_at
                FROM api_key_usage_snapshots
                WHERE api_key_id = :key_id
                ORDER BY synced_at DESC
                """
            ),
            {"key_id": key_id},
        ).mappings().all()
    return [dict(row) for row in rows]


def test_usage_sync_script_records_snapshot_history(client, admin_headers, user_headers, monkeypatch):
    from scripts import sync_api_key_usage

    settings = get_settings()
    db_url = settings.test_database_url or settings.database_url
    usage_engine = create_engine(db_url, future=True)
    monkeypatch.setattr(
        "scripts.sync_api_key_usage.SessionLocal",
        sessionmaker(bind=usage_engine, autoflush=False, autocommit=False, class_=Session),
    )

    whitelist_resp = client.post(
        _api("/whitelists"),
        headers=admin_headers,
        json={
            "sysid": int(user_headers["x-sysid"]),
            "account": user_headers["x-account"],
            "name": user_headers["x-name"],
            "email": user_headers["x-email"],
            "note": "seed",
        },
    )
    assert whitelist_resp.status_code == 201

    create_resp = client.post(
        _api("/api-keys/applications"),
        headers=user_headers,
        json={"application_date": str(date.today()), "duration_months": 1, "purpose": "sync usage"},
    )
    assert create_resp.status_code == 201
    item = client.get(_api("/api-keys"), headers=user_headers).json()["items"][0]
    key_id = item["id"]
    key_alias = item["key_alias"]

    synced_at = datetime.now(UTC).replace(microsecond=0)
    budget_reset_at = synced_at + timedelta(days=7)

    class _FakeProviderClient:
        def list_spend_logs(self, query: dict) -> dict:
            assert query["key_alias"] == key_alias
            return {
                "data": [
                    {
                        "status": "success",
                        "spend": 0.009805,
                        "prompt_tokens": 123,
                        "completion_tokens": 45,
                        "total_tokens": 168,
                        "startTime": synced_at.isoformat(),
                        "endTime": synced_at.isoformat(),
                    },
                    {
                        "status": "failure",
                        "spend": 99.0,
                        "prompt_tokens": 999,
                        "completion_tokens": 999,
                        "total_tokens": 1998,
                        "startTime": synced_at.isoformat(),
                        "endTime": synced_at.isoformat(),
                    },
                ],
                "total": 2,
                "page": 1,
                "page_size": 100,
                "total_pages": 1,
                "budget_reset_at": budget_reset_at.isoformat(),
            }

    monkeypatch.setattr(sync_api_key_usage, "ProviderClient", lambda: _FakeProviderClient())
    monkeypatch.setattr(
        sync_api_key_usage,
        "_now_utc",
        lambda: synced_at,
    )

    updated = sync_api_key_usage.run_once(batch_size=100, dry_run=False)

    assert updated == 1
    rows = _fetch_usage_snapshot_rows(key_id)
    assert len(rows) == 1
    assert float(rows[0]["spend"]) == 0.0098
    assert rows[0]["prompt_tokens"] == 123
    assert rows[0]["completion_tokens"] == 45
    assert rows[0]["total_tokens"] == 168
    assert rows[0]["budget_reset_at"].replace(tzinfo=UTC) == budget_reset_at
    assert rows[0]["synced_at"].replace(tzinfo=UTC) == synced_at

    listed = client.get(_api("/api-keys"), headers=user_headers)
    assert listed.status_code == 200
    assert listed.json()["items"][0]["usage_summary"]["spend"] == 0.01

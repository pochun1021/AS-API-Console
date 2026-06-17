from types import SimpleNamespace

from db.migrations import helpers


class _FakeInspector:
    def __init__(
        self,
        *,
        tables: list[str] | None = None,
        indexes: dict[str, list[str]] | None = None,
        checks: dict[str, list[str]] | None = None,
        foreign_keys: dict[str, list[str]] | None = None,
        uniques: dict[str, list[str]] | None = None,
    ) -> None:
        self.tables = tables or []
        self.indexes = indexes or {}
        self.checks = checks or {}
        self.foreign_keys = foreign_keys or {}
        self.uniques = uniques or {}

    def get_table_names(self) -> list[str]:
        return self.tables

    def get_columns(self, table_name: str) -> list[dict]:
        return []

    def get_indexes(self, table_name: str) -> list[dict]:
        return [{"name": name} for name in self.indexes.get(table_name, [])]

    def get_check_constraints(self, table_name: str) -> list[dict]:
        return [{"name": name} for name in self.checks.get(table_name, [])]

    def get_foreign_keys(self, table_name: str) -> list[dict]:
        return [{"name": name} for name in self.foreign_keys.get(table_name, [])]

    def get_unique_constraints(self, table_name: str) -> list[dict]:
        return [{"name": name} for name in self.uniques.get(table_name, [])]

    def get_pk_constraint(self, table_name: str) -> dict:
        return {"name": None}


def test_safe_drop_table_skips_missing_table(monkeypatch):
    monkeypatch.setattr(helpers, "get_inspector", lambda: _FakeInspector(tables=[]))
    calls: list[str] = []
    monkeypatch.setattr(helpers.op, "drop_table", lambda table_name: calls.append(table_name))

    helpers.safe_drop_table("notifications")

    assert calls == []


def test_safe_drop_index_only_drops_existing_index(monkeypatch):
    monkeypatch.setattr(
        helpers,
        "get_inspector",
        lambda: _FakeInspector(tables=["notifications"], indexes={"notifications": ["ix_notifications_user_id"]}),
    )
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        helpers.op,
        "drop_index",
        lambda index_name, *, table_name: calls.append((index_name, table_name)),
    )

    helpers.safe_drop_index("ix_notifications_user_id", table_name="notifications")
    helpers.safe_drop_index("ix_notifications_sysid", table_name="notifications")

    assert calls == [("ix_notifications_user_id", "notifications")]


def test_safe_drop_constraint_only_drops_existing_named_constraint(monkeypatch):
    monkeypatch.setattr(
        helpers,
        "get_inspector",
        lambda: _FakeInspector(
            tables=["api_key_usage_snapshots"],
            uniques={"api_key_usage_snapshots": ["uq_api_key_usage_snapshots_bucket"]},
        ),
    )
    calls: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        helpers.op,
        "drop_constraint",
        lambda constraint_name, table_name, *, type_: calls.append((constraint_name, table_name, type_)),
    )

    helpers.safe_drop_constraint(
        "uq_api_key_usage_snapshots_bucket",
        "api_key_usage_snapshots",
        type_="unique",
    )
    helpers.safe_drop_constraint(
        "missing_constraint",
        "api_key_usage_snapshots",
        type_="unique",
    )

    assert calls == [("uq_api_key_usage_snapshots_bucket", "api_key_usage_snapshots", "unique")]

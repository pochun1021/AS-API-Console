from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

import sqlalchemy as sa
from alembic import op

ConstraintType = Literal["check", "foreignkey", "primary", "unique"]


def get_inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def table_exists(table_name: str, *, inspector: sa.Inspector | None = None) -> bool:
    active_inspector = inspector or get_inspector()
    return table_name in set(active_inspector.get_table_names())


def column_exists(table_name: str, column_name: str, *, inspector: sa.Inspector | None = None) -> bool:
    active_inspector = inspector or get_inspector()
    if not table_exists(table_name, inspector=active_inspector):
        return False
    return column_name in {column["name"] for column in active_inspector.get_columns(table_name)}


def index_exists(table_name: str, index_name: str, *, inspector: sa.Inspector | None = None) -> bool:
    active_inspector = inspector or get_inspector()
    if not table_exists(table_name, inspector=active_inspector):
        return False
    return index_name in {index["name"] for index in active_inspector.get_indexes(table_name)}


def _named_constraints(constraints: Iterable[dict]) -> set[str]:
    return {constraint["name"] for constraint in constraints if constraint.get("name")}


def _current_schema_name(bind) -> str | None:
    if bind.dialect.name not in {"mysql", "mariadb"}:
        return None
    return bind.execute(sa.text("SELECT DATABASE()")).scalar_one_or_none()


def constraint_exists(
    table_name: str,
    constraint_name: str,
    *,
    type_: ConstraintType,
    inspector: sa.Inspector | None = None,
) -> bool:
    active_inspector = inspector or get_inspector()
    if not table_exists(table_name, inspector=active_inspector):
        return False

    bind = op.get_bind()
    schema_name = _current_schema_name(bind)
    if schema_name is not None:
        type_map = {
            "check": "CHECK",
            "foreignkey": "FOREIGN KEY",
            "unique": "UNIQUE",
            "primary": "PRIMARY KEY",
        }
        row = bind.execute(
            sa.text(
                """
                SELECT 1
                FROM information_schema.TABLE_CONSTRAINTS
                WHERE TABLE_SCHEMA = :schema_name
                  AND TABLE_NAME = :table_name
                  AND CONSTRAINT_NAME = :constraint_name
                  AND CONSTRAINT_TYPE = :constraint_type
                LIMIT 1
                """
            ),
            {
                "schema_name": schema_name,
                "table_name": table_name,
                "constraint_name": constraint_name,
                "constraint_type": type_map[type_],
            },
        ).first()
        return row is not None

    if type_ == "check":
        return constraint_name in _named_constraints(active_inspector.get_check_constraints(table_name))
    if type_ == "foreignkey":
        return constraint_name in _named_constraints(active_inspector.get_foreign_keys(table_name))
    if type_ == "unique":
        return constraint_name in _named_constraints(active_inspector.get_unique_constraints(table_name))
    if type_ == "primary":
        primary = active_inspector.get_pk_constraint(table_name)
        return primary.get("name") == constraint_name
    raise ValueError(f"Unsupported constraint type: {type_}")


def safe_drop_table(table_name: str, *, inspector: sa.Inspector | None = None) -> None:
    active_inspector = inspector or get_inspector()
    if table_exists(table_name, inspector=active_inspector):
        op.drop_table(table_name)


def safe_drop_index(index_name: str, *, table_name: str, inspector: sa.Inspector | None = None) -> None:
    active_inspector = inspector or get_inspector()
    if index_exists(table_name, index_name, inspector=active_inspector):
        op.drop_index(index_name, table_name=table_name)


def safe_drop_constraint(
    constraint_name: str,
    table_name: str,
    *,
    type_: ConstraintType,
    inspector: sa.Inspector | None = None,
) -> None:
    active_inspector = inspector or get_inspector()
    if constraint_exists(table_name, constraint_name, type_=type_, inspector=active_inspector):
        op.drop_constraint(constraint_name, table_name, type_=type_)

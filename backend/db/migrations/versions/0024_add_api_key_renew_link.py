"""add api key renewed link column

Revision ID: 0024_api_key_renew_link
Revises: 0023_rm_notifications_issue_mode
Create Date: 2026-05-20 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024_api_key_renew_link"
down_revision: str | None = "0023_rm_notifications_issue_mode"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in set(inspector.get_table_names())


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in set(inspector.get_table_names()):
        return False
    return column in {col["name"] for col in inspector.get_columns(table)}


def _index_exists(table: str, index: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in set(inspector.get_table_names()):
        return False
    return index in {idx["name"] for idx in inspector.get_indexes(table)}


def _foreign_key_exists(table: str, constrained_columns: list[str]) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in set(inspector.get_table_names()):
        return False
    targets = set(constrained_columns)
    for fk in inspector.get_foreign_keys(table):
        if set(fk.get("constrained_columns") or []) == targets:
            return True
    return False


def upgrade() -> None:
    if not _table_exists("api_keys"):
        return

    if not _column_exists("api_keys", "renewed_to_key_id"):
        op.add_column("api_keys", sa.Column("renewed_to_key_id", sa.String(length=36), nullable=True))

    if not _index_exists("api_keys", "ix_api_keys_renewed_to_key_id"):
        op.create_index("ix_api_keys_renewed_to_key_id", "api_keys", ["renewed_to_key_id"], unique=False)

    if not _foreign_key_exists("api_keys", ["renewed_to_key_id"]):
        op.create_foreign_key(
            "fk_api_keys_renewed_to_key_id",
            "api_keys",
            "api_keys",
            ["renewed_to_key_id"],
            ["id"],
        )


def downgrade() -> None:
    if not _table_exists("api_keys"):
        return

    op.drop_constraint("fk_api_keys_renewed_to_key_id", "api_keys", type_="foreignkey")
    if _index_exists("api_keys", "ix_api_keys_renewed_to_key_id"):
        op.drop_index("ix_api_keys_renewed_to_key_id", table_name="api_keys")
    if _column_exists("api_keys", "renewed_to_key_id"):
        op.drop_column("api_keys", "renewed_to_key_id")

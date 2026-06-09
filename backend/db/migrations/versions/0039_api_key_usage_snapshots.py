"""add api key usage snapshots history table

Revision ID: 0039_api_key_usage_snapshots
Revises: 0038_api_key_usage_cache
Create Date: 2026-06-09 15:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0039_api_key_usage_snapshots"
down_revision: str | None = "0038_api_key_usage_cache"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_key_usage_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("api_key_id", sa.String(length=36), nullable=False),
        sa.Column("spend", sa.Numeric(12, 4), nullable=True),
        sa.Column("budget_reset_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_key_usage_snapshots_api_key_id", "api_key_usage_snapshots", ["api_key_id"], unique=False)
    op.create_index("ix_api_key_usage_snapshots_synced_at", "api_key_usage_snapshots", ["synced_at"], unique=False)

    op.execute(
        sa.text(
            """
            INSERT INTO api_key_usage_snapshots (id, api_key_id, spend, budget_reset_at, synced_at, created_at)
            SELECT UUID(), id, usage_spend, usage_budget_reset_at, usage_synced_at, COALESCE(usage_synced_at, created_at)
            FROM api_keys
            WHERE usage_synced_at IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_api_key_usage_snapshots_synced_at", table_name="api_key_usage_snapshots")
    op.drop_index("ix_api_key_usage_snapshots_api_key_id", table_name="api_key_usage_snapshots")
    op.drop_table("api_key_usage_snapshots")

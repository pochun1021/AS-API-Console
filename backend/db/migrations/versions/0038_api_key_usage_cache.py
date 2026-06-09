"""add api key usage cache columns

Revision ID: 0038_api_key_usage_cache
Revises: 0037_inst_sync_control
Create Date: 2026-06-09 12:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0038_api_key_usage_cache"
down_revision: str | None = "0037_inst_sync_control"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("api_keys", sa.Column("usage_spend", sa.Numeric(12, 4), nullable=True))
    op.add_column("api_keys", sa.Column("usage_budget_reset_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("api_keys", sa.Column("usage_synced_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("api_keys", "usage_synced_at")
    op.drop_column("api_keys", "usage_budget_reset_at")
    op.drop_column("api_keys", "usage_spend")

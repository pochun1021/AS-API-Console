"""reorder api key usage snapshot columns

Revision ID: 0041_usage_snapshot_col_order
Revises: 0040_usage_snapshot_tokens
Create Date: 2026-06-09 17:05:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0041_usage_snapshot_col_order"
down_revision: str | None = "0040_usage_snapshot_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE api_key_usage_snapshots
            MODIFY COLUMN prompt_tokens BIGINT NOT NULL DEFAULT 0 AFTER spend,
            MODIFY COLUMN completion_tokens BIGINT NOT NULL DEFAULT 0 AFTER prompt_tokens,
            MODIFY COLUMN total_tokens BIGINT NOT NULL DEFAULT 0 AFTER completion_tokens
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE api_key_usage_snapshots
            MODIFY COLUMN prompt_tokens BIGINT NOT NULL DEFAULT 0 AFTER created_at,
            MODIFY COLUMN completion_tokens BIGINT NOT NULL DEFAULT 0 AFTER prompt_tokens,
            MODIFY COLUMN total_tokens BIGINT NOT NULL DEFAULT 0 AFTER completion_tokens
            """
        )
    )

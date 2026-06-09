"""add token fields to api key usage snapshots

Revision ID: 0040_usage_snapshot_tokens
Revises: 0039_api_key_usage_snapshots
Create Date: 2026-06-09 16:20:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0040_usage_snapshot_tokens"
down_revision: str | None = "0039_api_key_usage_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "api_key_usage_snapshots",
        sa.Column("prompt_tokens", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "api_key_usage_snapshots",
        sa.Column("completion_tokens", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "api_key_usage_snapshots",
        sa.Column("total_tokens", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_column("api_key_usage_snapshots", "total_tokens")
    op.drop_column("api_key_usage_snapshots", "completion_tokens")
    op.drop_column("api_key_usage_snapshots", "prompt_tokens")

"""add api_keys usage token mirror columns

Revision ID: 0045_api_key_usage_tokens
Revises: 0044_usage_daily_buckets
Create Date: 2026-06-18 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0045_api_key_usage_tokens"
down_revision: str | None = "0044_usage_daily_buckets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("api_keys", sa.Column("usage_prompt_tokens", sa.BigInteger(), nullable=True))
    op.add_column("api_keys", sa.Column("usage_completion_tokens", sa.BigInteger(), nullable=True))
    op.add_column("api_keys", sa.Column("usage_total_tokens", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("api_keys", "usage_total_tokens")
    op.drop_column("api_keys", "usage_completion_tokens")
    op.drop_column("api_keys", "usage_prompt_tokens")

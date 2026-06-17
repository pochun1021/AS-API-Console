"""add usage snapshot daily bucket columns

Revision ID: 0044_usage_daily_buckets
Revises: 0043_duration_days_contract
Create Date: 2026-06-16 11:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from db.migrations.helpers import safe_drop_constraint, safe_drop_index

revision: str = "0044_usage_daily_buckets"
down_revision: str | None = "0043_duration_days_contract"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "api_key_usage_snapshots",
        sa.Column("bucket_granularity", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "api_key_usage_snapshots",
        sa.Column("bucket_start_utc", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "api_key_usage_snapshots",
        sa.Column("bucket_end_utc", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_api_key_usage_snapshots_bucket_start_utc",
        "api_key_usage_snapshots",
        ["bucket_start_utc"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_api_key_usage_snapshots_bucket",
        "api_key_usage_snapshots",
        ["api_key_id", "bucket_granularity", "bucket_start_utc"],
    )


def downgrade() -> None:
    safe_drop_constraint("uq_api_key_usage_snapshots_bucket", "api_key_usage_snapshots", type_="unique")
    safe_drop_index("ix_api_key_usage_snapshots_bucket_start_utc", table_name="api_key_usage_snapshots")
    op.drop_column("api_key_usage_snapshots", "bucket_end_utc")
    op.drop_column("api_key_usage_snapshots", "bucket_start_utc")
    op.drop_column("api_key_usage_snapshots", "bucket_granularity")

"""add announcements table

Revision ID: 0042_add_announcements
Revises: 0041_usage_snapshot_col_order
Create Date: 2026-06-15 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from db.migrations.helpers import safe_drop_index, safe_drop_table

revision: str = "0042_add_announcements"
down_revision: str | None = "0037_app_orig_duration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "announcements",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("publish_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("publish_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=100), nullable=False),
        sa.Column("updated_by", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status in ('active', 'inactive')", name="ck_announcements_status"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_announcements_status", "announcements", ["status"], unique=False)
    op.create_index("ix_announcements_publish_from", "announcements", ["publish_from"], unique=False)
    op.create_index("ix_announcements_publish_to", "announcements", ["publish_to"], unique=False)
    op.create_index("ix_announcements_updated_at", "announcements", ["updated_at"], unique=False)


def downgrade() -> None:
    safe_drop_index("ix_announcements_updated_at", table_name="announcements")
    safe_drop_index("ix_announcements_publish_to", table_name="announcements")
    safe_drop_index("ix_announcements_publish_from", table_name="announcements")
    safe_drop_index("ix_announcements_status", table_name="announcements")
    safe_drop_table("announcements")

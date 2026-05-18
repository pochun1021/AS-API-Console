"""add user_preferences table

Revision ID: 0018_user_preferences
Revises: 0017_auth_audit_logs
Create Date: 2026-05-18 15:45:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_user_preferences"
down_revision: str | None = "0017_auth_audit_logs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_preferences",
        sa.Column("sysid", sa.String(length=100), nullable=False),
        sa.Column("preferred_locale", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("preferred_locale in ('zh-TW', 'en')", name="ck_user_preferences_locale"),
        sa.PrimaryKeyConstraint("sysid"),
    )
    op.create_index("ix_user_preferences_sysid", "user_preferences", ["sysid"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_preferences_sysid", table_name="user_preferences")
    op.drop_table("user_preferences")

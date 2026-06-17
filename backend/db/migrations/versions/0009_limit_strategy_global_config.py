"""add limit strategy global config

Revision ID: 0009_ls_global_cfg
Revises: 0008_strategy_templates
Create Date: 2026-05-16 14:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from db.migrations.helpers import safe_drop_table

revision: str = "0009_ls_global_cfg"
down_revision: str | None = "0008_strategy_templates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "limit_strategy_config",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("active_mode", sa.String(length=20), nullable=False, server_default="budget"),
        sa.Column("budget_max_budget", sa.String(length=100), nullable=False, server_default="1000"),
        sa.Column("budget_duration", sa.String(length=20), nullable=False, server_default="monthly"),
        sa.Column("rate_limit_tpm", sa.Integer(), nullable=False, server_default="10000"),
        sa.Column("rate_limit_rpm", sa.Integer(), nullable=False, server_default="500"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("active_mode in ('budget', 'rate_limit')", name="ck_limit_strategy_config_active_mode"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        """
        INSERT INTO limit_strategy_config
            (id, active_mode, budget_max_budget, budget_duration, rate_limit_tpm, rate_limit_rpm, created_at, updated_at)
        VALUES
            ('global-limit-strategy-config', 'budget', '1000', 'monthly', 10000, 500, NOW(), NOW())
        """
    )


def downgrade() -> None:
    safe_drop_table("limit_strategy_config")

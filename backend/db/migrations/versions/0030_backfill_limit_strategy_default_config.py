"""backfill default limit strategy config row

Revision ID: 0030_limit_cfg_default
Revises: 0029_whitelist_add_account_name
Create Date: 2026-06-01 17:05:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030_limit_cfg_default"
down_revision: str | None = "0029_whitelist_add_account_name"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONFIG_ID = "global-limit-strategy-config"


def upgrade() -> None:
    bind = op.get_bind()
    exists = bind.execute(
        sa.text("SELECT 1 FROM limit_strategy_config WHERE id = :id LIMIT 1"),
        {"id": _CONFIG_ID},
    ).scalar_one_or_none()
    if exists is not None:
        return

    op.execute(
        sa.text(
            """
            INSERT INTO limit_strategy_config
                (id, budget_max_budget, budget_duration, rate_limit_tpm, rate_limit_rpm, created_at, updated_at)
            VALUES
                (:id, '1000', 'monthly', 10000, 500, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        ),
        {"id": _CONFIG_ID},
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM limit_strategy_config WHERE id = :id"), {"id": _CONFIG_ID})

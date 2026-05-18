"""remove pending error columns and active mode

Revision ID: 0011_rm_pending_active
Revises: 0010_application_selected_mode
Create Date: 2026-05-16 15:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_rm_pending_active"
down_revision: str | None = "0010_application_selected_mode"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    app_columns = {col["name"] for col in inspector.get_columns("api_key_applications")}
    if "provider_error_code" in app_columns:
        op.drop_column("api_key_applications", "provider_error_code")
    if "provider_error_message" in app_columns:
        op.drop_column("api_key_applications", "provider_error_message")

    cfg_columns = {col["name"] for col in inspector.get_columns("limit_strategy_config")}
    if "active_mode" in cfg_columns:
        try:
            op.drop_constraint("ck_limit_strategy_config_active_mode", "limit_strategy_config", type_="check")
        except Exception:
            pass
        op.drop_column("limit_strategy_config", "active_mode")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    cfg_columns = {col["name"] for col in inspector.get_columns("limit_strategy_config")}
    if "active_mode" not in cfg_columns:
        op.add_column(
            "limit_strategy_config",
            sa.Column("active_mode", sa.String(length=20), nullable=False, server_default="budget"),
        )
        try:
            op.create_check_constraint(
                "ck_limit_strategy_config_active_mode",
                "limit_strategy_config",
                "active_mode in ('budget', 'rate_limit')",
            )
        except Exception:
            pass

    app_columns = {col["name"] for col in inspector.get_columns("api_key_applications")}
    if "provider_error_code" not in app_columns:
        op.add_column("api_key_applications", sa.Column("provider_error_code", sa.String(length=50), nullable=True))
    if "provider_error_message" not in app_columns:
        op.add_column("api_key_applications", sa.Column("provider_error_message", sa.Text(), nullable=True))

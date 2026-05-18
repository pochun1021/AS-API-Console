"""add limit strategy templates and application binding

Revision ID: 0008_strategy_templates
Revises: 0007_app_strategy_pending
Create Date: 2026-05-16 10:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_strategy_templates"
down_revision: str | None = "0007_app_strategy_pending"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "limit_strategy_templates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("strategy_type", sa.String(length=20), nullable=False),
        sa.Column("max_budget", sa.String(length=100), nullable=True),
        sa.Column("budget_duration", sa.String(length=20), nullable=True),
        sa.Column("tpm_limit", sa.Integer(), nullable=True),
        sa.Column("rpm_limit", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_by", sa.String(length=100), nullable=False),
        sa.Column("updated_by", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("strategy_type in ('budget', 'rate_limit')", name="ck_limit_strategy_templates_type"),
        sa.CheckConstraint("status in ('active', 'inactive')", name="ck_limit_strategy_templates_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.execute(
        """
        INSERT INTO limit_strategy_templates
            (id, name, strategy_type, max_budget, budget_duration, tpm_limit, rpm_limit, status, created_by, updated_by, created_at, updated_at)
        VALUES
            ('default-budget-template', 'default-budget-template', 'budget', '1000', 'monthly', NULL, NULL, 'active', 'system', 'system', NOW(), NOW())
        """
    )

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    app_cols = {col["name"] for col in inspector.get_columns("api_key_applications")}
    if "limit_strategy_template_id" not in app_cols:
        op.add_column("api_key_applications", sa.Column("limit_strategy_template_id", sa.String(length=36), nullable=True))
        op.create_index(
            "ix_api_key_applications_limit_strategy_template_id",
            "api_key_applications",
            ["limit_strategy_template_id"],
            unique=False,
        )
        op.create_foreign_key(
            "fk_applications_limit_strategy_template_id",
            "api_key_applications",
            "limit_strategy_templates",
            ["limit_strategy_template_id"],
            ["id"],
        )


def downgrade() -> None:
    op.drop_constraint("fk_applications_limit_strategy_template_id", "api_key_applications", type_="foreignkey")
    op.drop_index("ix_api_key_applications_limit_strategy_template_id", table_name="api_key_applications")
    op.drop_column("api_key_applications", "limit_strategy_template_id")
    op.drop_table("limit_strategy_templates")

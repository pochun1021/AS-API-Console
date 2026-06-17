"""remove limit strategy templates and app binding column

Revision ID: 0013_rm_limit_strategy_templates
Revises: 0012_notifications
Create Date: 2026-05-15 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from db.migrations.helpers import safe_drop_constraint, safe_drop_index, safe_drop_table

revision: str = "0013_rm_limit_strategy_templates"
down_revision: str | None = "0012_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_tables = set(inspector.get_table_names())
    if "api_key_applications" in existing_tables:
        app_columns = {col["name"] for col in inspector.get_columns("api_key_applications")}
        if "limit_strategy_template_id" in app_columns:
            existing_fks = {fk.get("name") for fk in inspector.get_foreign_keys("api_key_applications")}
            if "fk_applications_limit_strategy_template_id" in existing_fks:
                safe_drop_constraint(
                    "fk_applications_limit_strategy_template_id",
                    "api_key_applications",
                    type_="foreignkey",
                )

            existing_indexes = {idx["name"] for idx in inspector.get_indexes("api_key_applications")}
            if "ix_api_key_applications_limit_strategy_template_id" in existing_indexes:
                safe_drop_index("ix_api_key_applications_limit_strategy_template_id", table_name="api_key_applications")

            op.drop_column("api_key_applications", "limit_strategy_template_id")

    if "limit_strategy_templates" in existing_tables:
        safe_drop_table("limit_strategy_templates")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_tables = set(inspector.get_table_names())
    if "limit_strategy_templates" not in existing_tables:
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

    if "api_key_applications" in existing_tables:
        app_columns = {col["name"] for col in inspector.get_columns("api_key_applications")}
        if "limit_strategy_template_id" not in app_columns:
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

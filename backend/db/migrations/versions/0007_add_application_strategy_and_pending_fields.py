"""add application strategy and pending issuance fields

Revision ID: 0007_app_strategy_pending
Revises: 0006_add_api_key_alias
Create Date: 2026-05-15 18:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_app_strategy_pending"
down_revision: str | None = "0006_add_api_key_alias"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("api_key_applications")}

    if "limit_strategy" not in existing_columns:
        op.add_column("api_key_applications", sa.Column("limit_strategy", sa.String(length=20), nullable=True))
        op.execute("UPDATE api_key_applications SET limit_strategy='budget' WHERE limit_strategy IS NULL")
        op.alter_column(
            "api_key_applications",
            "limit_strategy",
            existing_type=sa.String(length=20),
            nullable=False,
        )
    if "max_budget" not in existing_columns:
        op.add_column("api_key_applications", sa.Column("max_budget", sa.String(length=100), nullable=True))
    if "budget_duration" not in existing_columns:
        op.add_column("api_key_applications", sa.Column("budget_duration", sa.String(length=20), nullable=True))
    if "tpm_limit" not in existing_columns:
        op.add_column("api_key_applications", sa.Column("tpm_limit", sa.Integer(), nullable=True))
    if "rpm_limit" not in existing_columns:
        op.add_column("api_key_applications", sa.Column("rpm_limit", sa.Integer(), nullable=True))
    if "issuance_status" not in existing_columns:
        op.add_column("api_key_applications", sa.Column("issuance_status", sa.String(length=20), nullable=True))
        op.execute("UPDATE api_key_applications SET issuance_status='issued' WHERE issuance_status IS NULL")
        op.alter_column(
            "api_key_applications",
            "issuance_status",
            existing_type=sa.String(length=20),
            nullable=False,
        )
    if "provider_error_code" not in existing_columns:
        op.add_column("api_key_applications", sa.Column("provider_error_code", sa.String(length=50), nullable=True))
    if "provider_error_message" not in existing_columns:
        op.add_column("api_key_applications", sa.Column("provider_error_message", sa.Text(), nullable=True))
    if "pending_issued_at" not in existing_columns:
        op.add_column("api_key_applications", sa.Column("pending_issued_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("api_key_applications", "pending_issued_at")
    op.drop_column("api_key_applications", "provider_error_message")
    op.drop_column("api_key_applications", "provider_error_code")
    op.drop_column("api_key_applications", "issuance_status")
    op.drop_column("api_key_applications", "rpm_limit")
    op.drop_column("api_key_applications", "tpm_limit")
    op.drop_column("api_key_applications", "budget_duration")
    op.drop_column("api_key_applications", "max_budget")
    op.drop_column("api_key_applications", "limit_strategy")

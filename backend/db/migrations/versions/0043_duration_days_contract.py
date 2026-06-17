"""switch api key durations to day-based contract

Revision ID: 0043_duration_days_contract
Revises: 0042_add_announcements
Create Date: 2026-06-15 16:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from db.migrations.helpers import constraint_exists

revision: str = "0043_duration_days_contract"
down_revision: str | None = "0042_add_announcements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _drop_check_constraint_if_exists(name: str) -> None:
    if constraint_exists("api_key_applications", name, type_="check"):
        op.execute(sa.text(f"ALTER TABLE api_key_applications DROP CONSTRAINT {name}"))


def upgrade() -> None:
    _drop_check_constraint_if_exists("ck_applications_duration_months")
    _drop_check_constraint_if_exists("ck_applications_original_duration_months")

    op.execute(
        """
        UPDATE api_key_applications
        SET duration_months = CASE duration_months
            WHEN 1 THEN 30
            WHEN 6 THEN 180
            WHEN 12 THEN 360
            ELSE duration_months
        END,
        original_duration_months = CASE original_duration_months
            WHEN 1 THEN 30
            WHEN 6 THEN 180
            WHEN 12 THEN 360
            ELSE original_duration_months
        END
        """
    )

    op.alter_column(
        "api_key_applications",
        "duration_months",
        new_column_name="duration_days",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )
    op.alter_column(
        "api_key_applications",
        "original_duration_months",
        new_column_name="original_duration_days",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )
    op.create_check_constraint("ck_applications_duration_days", "api_key_applications", "duration_days in (30, 180, 360)")
    op.create_check_constraint(
        "ck_applications_original_duration_days",
        "api_key_applications",
        "original_duration_days in (30, 180, 360)",
    )


def downgrade() -> None:
    _drop_check_constraint_if_exists("ck_applications_duration_days")
    _drop_check_constraint_if_exists("ck_applications_original_duration_days")
    op.alter_column(
        "api_key_applications",
        "duration_days",
        new_column_name="duration_months",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )
    op.alter_column(
        "api_key_applications",
        "original_duration_days",
        new_column_name="original_duration_months",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )

    op.execute(
        """
        UPDATE api_key_applications
        SET duration_months = CASE duration_months
            WHEN 30 THEN 1
            WHEN 180 THEN 6
            WHEN 360 THEN 12
            ELSE duration_months
        END,
        original_duration_months = CASE original_duration_months
            WHEN 30 THEN 1
            WHEN 180 THEN 6
            WHEN 360 THEN 12
            ELSE original_duration_months
        END
        """
    )

    op.create_check_constraint("ck_applications_duration_months", "api_key_applications", "duration_months > 0")
    op.create_check_constraint(
        "ck_applications_original_duration_months",
        "api_key_applications",
        "original_duration_months > 0",
    )

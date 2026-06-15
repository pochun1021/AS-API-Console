"""switch api key durations to day-based contract

Revision ID: 0043_duration_days_contract
Revises: 0042_add_announcements
Create Date: 2026-06-15 16:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0043_duration_days_contract"
down_revision: str | None = "0042_add_announcements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("api_key_applications") as batch_op:
        batch_op.drop_constraint("ck_applications_duration_months", type_="check")
        batch_op.drop_constraint("ck_applications_original_duration_months", type_="check")

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

    with op.batch_alter_table("api_key_applications") as batch_op:
        batch_op.alter_column("duration_months", new_column_name="duration_days", existing_type=sa.Integer())
        batch_op.alter_column(
            "original_duration_months",
            new_column_name="original_duration_days",
            existing_type=sa.Integer(),
        )
        batch_op.create_check_constraint("ck_applications_duration_days", "duration_days in (30, 180, 360)")
        batch_op.create_check_constraint(
            "ck_applications_original_duration_days",
            "original_duration_days in (30, 180, 360)",
        )


def downgrade() -> None:
    with op.batch_alter_table("api_key_applications") as batch_op:
        batch_op.drop_constraint("ck_applications_duration_days", type_="check")
        batch_op.drop_constraint("ck_applications_original_duration_days", type_="check")
        batch_op.alter_column("duration_days", new_column_name="duration_months", existing_type=sa.Integer())
        batch_op.alter_column(
            "original_duration_days",
            new_column_name="original_duration_months",
            existing_type=sa.Integer(),
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

    with op.batch_alter_table("api_key_applications") as batch_op:
        batch_op.create_check_constraint("ck_applications_duration_months", "duration_months > 0")
        batch_op.create_check_constraint(
            "ck_applications_original_duration_months",
            "original_duration_months > 0",
        )

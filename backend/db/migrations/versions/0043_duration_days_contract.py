"""switch api key durations to day-based contract

Revision ID: 0043_duration_days_contract
Revises: 0042_add_announcements
Create Date: 2026-06-15 16:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from db.migrations.helpers import column_exists, constraint_exists

revision: str = "0043_duration_days_contract"
down_revision: str | None = "0042_add_announcements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _drop_check_constraint_if_exists(name: str) -> None:
    if constraint_exists("api_key_applications", name, type_="check"):
        op.execute(sa.text(f"ALTER TABLE api_key_applications DROP CONSTRAINT {name}"))


def _current_duration_columns() -> tuple[str, str]:
    duration_column = "duration_days" if column_exists("api_key_applications", "duration_days") else "duration_months"
    original_duration_column = (
        "original_duration_days"
        if column_exists("api_key_applications", "original_duration_days")
        else "original_duration_months"
    )
    return duration_column, original_duration_column


def _normalized_duration_sql(column_name: str) -> str:
    return f"""
        CASE
            WHEN {column_name} IN (30, 180, 360) THEN {column_name}
            WHEN {column_name} = 1 THEN 30
            WHEN {column_name} = 6 THEN 180
            WHEN {column_name} = 12 THEN 360
            WHEN {column_name} IS NULL OR {column_name} <= 0 THEN 30
            WHEN {column_name} < 30 THEN 30
            WHEN {column_name} < 180 THEN 180
            ELSE 360
        END
    """


def _effective_duration_sql(duration_column: str, original_duration_column: str) -> str:
    normalized_original = _normalized_duration_sql(original_duration_column)
    return f"""
        CASE
            WHEN {duration_column} IN (30, 180, 360) THEN {duration_column}
            WHEN {duration_column} IN (1, 6, 12) THEN {_normalized_duration_sql(duration_column)}
            ELSE {normalized_original}
        END
    """


def upgrade() -> None:
    _drop_check_constraint_if_exists("ck_applications_duration_months")
    _drop_check_constraint_if_exists("ck_applications_original_duration_months")
    duration_column, original_duration_column = _current_duration_columns()

    op.execute(
        sa.text(
            f"""
        UPDATE api_key_applications
        SET {duration_column} = {_effective_duration_sql(duration_column, original_duration_column)},
            {original_duration_column} = {_normalized_duration_sql(original_duration_column)}
        """
        )
    )

    if duration_column == "duration_months":
        op.alter_column(
            "api_key_applications",
            "duration_months",
            new_column_name="duration_days",
            existing_type=sa.Integer(),
            existing_nullable=False,
        )
    if original_duration_column == "original_duration_months":
        op.alter_column(
            "api_key_applications",
            "original_duration_months",
            new_column_name="original_duration_days",
            existing_type=sa.Integer(),
            existing_nullable=False,
        )
    if not constraint_exists("api_key_applications", "ck_applications_duration_days", type_="check"):
        op.create_check_constraint("ck_applications_duration_days", "api_key_applications", "duration_days in (30, 180, 360)")
    if not constraint_exists("api_key_applications", "ck_applications_original_duration_days", type_="check"):
        op.create_check_constraint(
            "ck_applications_original_duration_days",
            "api_key_applications",
            "original_duration_days in (30, 180, 360)",
        )


def downgrade() -> None:
    _drop_check_constraint_if_exists("ck_applications_duration_days")
    _drop_check_constraint_if_exists("ck_applications_original_duration_days")
    duration_column, original_duration_column = _current_duration_columns()
    if duration_column == "duration_days":
        op.alter_column(
            "api_key_applications",
            "duration_days",
            new_column_name="duration_months",
            existing_type=sa.Integer(),
            existing_nullable=False,
        )
    if original_duration_column == "original_duration_days":
        op.alter_column(
            "api_key_applications",
            "original_duration_days",
            new_column_name="original_duration_months",
            existing_type=sa.Integer(),
            existing_nullable=False,
        )
    duration_column, original_duration_column = _current_duration_columns()

    op.execute(
        sa.text(
            f"""
        UPDATE api_key_applications
        SET {duration_column} = CASE {duration_column}
            WHEN 30 THEN 1
            WHEN 180 THEN 6
            WHEN 360 THEN 12
            ELSE {duration_column}
        END,
        {original_duration_column} = CASE {original_duration_column}
            WHEN 30 THEN 1
            WHEN 180 THEN 6
            WHEN 360 THEN 12
            ELSE {original_duration_column}
        END
        """
        )
    )

    if not constraint_exists("api_key_applications", "ck_applications_duration_months", type_="check"):
        op.create_check_constraint("ck_applications_duration_months", "api_key_applications", "duration_months > 0")
    if not constraint_exists("api_key_applications", "ck_applications_original_duration_months", type_="check"):
        op.create_check_constraint(
            "ck_applications_original_duration_months",
            "api_key_applications",
            "original_duration_months > 0",
        )

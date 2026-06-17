"""add original_duration_months to api_key_applications

Revision ID: 0037_app_orig_duration
Revises: 0041_usage_snapshot_col_order
Create Date: 2026-06-11 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from db.migrations.helpers import constraint_exists

revision: str = "0037_app_orig_duration"
down_revision: str | None = "0041_usage_snapshot_col_order"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("api_key_applications") as batch_op:
        batch_op.add_column(sa.Column("original_duration_months", sa.Integer(), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE api_key_applications
            SET original_duration_months = duration_months
            WHERE original_duration_months IS NULL
            """
        )
    )

    with op.batch_alter_table("api_key_applications") as batch_op:
        batch_op.alter_column("original_duration_months", existing_type=sa.Integer(), nullable=False)
        batch_op.create_check_constraint(
            "ck_applications_original_duration_months",
            "original_duration_months > 0",
        )


def downgrade() -> None:
    with op.batch_alter_table("api_key_applications") as batch_op:
        if constraint_exists("api_key_applications", "ck_applications_original_duration_months", type_="check"):
            batch_op.drop_constraint("ck_applications_original_duration_months", type_="check")
        batch_op.drop_column("original_duration_months")

"""relax application duration_months check

Revision ID: 0035_app_duration_positive
Revises: 0034_op_audit_err_detail
Create Date: 2026-06-04 16:15:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0035_app_duration_positive"
down_revision: str | None = "0034_op_audit_err_detail"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("api_key_applications") as batch_op:
        batch_op.drop_constraint("ck_applications_duration_months", type_="check")
        batch_op.create_check_constraint("ck_applications_duration_months", "duration_months > 0")


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE api_key_applications
            SET duration_months = 12
            WHERE duration_months NOT IN (1, 6, 12)
            """
        )
    )
    with op.batch_alter_table("api_key_applications") as batch_op:
        batch_op.drop_constraint("ck_applications_duration_months", type_="check")
        batch_op.create_check_constraint("ck_applications_duration_months", "duration_months in (1, 6, 12)")

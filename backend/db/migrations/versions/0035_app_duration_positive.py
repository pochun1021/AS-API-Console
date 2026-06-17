"""relax application duration_months check

Revision ID: 0035_app_duration_positive
Revises: 0034_op_audit_err_detail
Create Date: 2026-06-04 16:15:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from db.migrations.helpers import constraint_exists


revision: str = "0035_app_duration_positive"
down_revision: str | None = "0034_op_audit_err_detail"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _drop_check_constraint_if_exists(name: str) -> None:
    if constraint_exists("api_key_applications", name, type_="check"):
        op.execute(sa.text(f"ALTER TABLE api_key_applications DROP CONSTRAINT {name}"))


def upgrade() -> None:
    _drop_check_constraint_if_exists("ck_applications_duration_months")
    op.create_check_constraint("ck_applications_duration_months", "api_key_applications", "duration_months > 0")


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
    _drop_check_constraint_if_exists("ck_applications_duration_months")
    op.create_check_constraint(
        "ck_applications_duration_months",
        "api_key_applications",
        "duration_months in (1, 6, 12)",
    )

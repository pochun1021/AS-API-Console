"""add error_detail to operation_audit_logs

Revision ID: 0034_op_audit_err_detail
Revises: 0033_api_key_exp_notices
Create Date: 2026-06-04 13:10:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0034_op_audit_err_detail"
down_revision: str | None = "0033_api_key_exp_notices"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("operation_audit_logs") as batch_op:
        batch_op.add_column(sa.Column("error_detail", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("operation_audit_logs") as batch_op:
        batch_op.drop_column("error_detail")

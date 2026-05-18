"""add operator fields for proxy application submission

Revision ID: 0020_application_operator
Revises: 0019_whitelist_sysid
Create Date: 2026-05-18 17:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020_application_operator"
down_revision: str | None = "0019_whitelist_sysid"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("api_key_applications", sa.Column("is_proxy_submission", sa.Boolean(), nullable=True))
    op.add_column("api_key_applications", sa.Column("operator_account", sa.String(length=100), nullable=True))
    op.add_column("api_key_applications", sa.Column("operator_name", sa.String(length=100), nullable=True))
    op.add_column("api_key_applications", sa.Column("operator_email", sa.String(length=255), nullable=True))
    op.add_column("api_key_applications", sa.Column("operator_department", sa.String(length=100), nullable=True))
    op.add_column("api_key_applications", sa.Column("operator_sysid", sa.String(length=100), nullable=True))

    op.execute(
        """
        UPDATE api_key_applications
        SET
          is_proxy_submission = FALSE,
          operator_account = account,
          operator_name = name,
          operator_email = email,
          operator_department = department,
          operator_sysid = sysid
        """
    )

    with op.batch_alter_table("api_key_applications") as batch_op:
        batch_op.alter_column("is_proxy_submission", existing_type=sa.Boolean(), nullable=False)
        batch_op.alter_column("operator_account", existing_type=sa.String(length=100), nullable=False)
        batch_op.alter_column("operator_name", existing_type=sa.String(length=100), nullable=False)
        batch_op.alter_column("operator_email", existing_type=sa.String(length=255), nullable=False)
        batch_op.alter_column("operator_department", existing_type=sa.String(length=100), nullable=False)
        batch_op.alter_column("operator_sysid", existing_type=sa.String(length=100), nullable=False)

    op.create_index("ix_api_key_applications_operator_sysid", "api_key_applications", ["operator_sysid"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_api_key_applications_operator_sysid", table_name="api_key_applications")
    op.drop_column("api_key_applications", "operator_sysid")
    op.drop_column("api_key_applications", "operator_department")
    op.drop_column("api_key_applications", "operator_email")
    op.drop_column("api_key_applications", "operator_name")
    op.drop_column("api_key_applications", "operator_account")
    op.drop_column("api_key_applications", "is_proxy_submission")

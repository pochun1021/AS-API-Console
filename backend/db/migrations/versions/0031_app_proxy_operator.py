"""simplify application proxy submission fields

Revision ID: 0031_app_proxy_operator
Revises: 0030_limit_cfg_default
Create Date: 2026-06-02 13:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from db.migrations.helpers import safe_drop_index

revision: str = "0031_app_proxy_operator"
down_revision: str | None = "0030_limit_cfg_default"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(inspector: sa.Inspector, table: str, column: str) -> bool:
    return column in {item["name"] for item in inspector.get_columns(table)}


def _has_index(inspector: sa.Inspector, table: str, index: str) -> bool:
    return index in {item["name"] for item in inspector.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "api_key_applications", "proxy_operator_account"):
        op.add_column("api_key_applications", sa.Column("proxy_operator_account", sa.String(length=100), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE api_key_applications
            SET proxy_operator_account = CASE
                WHEN is_proxy_submission = TRUE THEN operator_account
                ELSE NULL
            END
            """
        )
    )

    if _has_index(inspector, "api_key_applications", "ix_api_key_applications_operator_sysid"):
        safe_drop_index("ix_api_key_applications_operator_sysid", table_name="api_key_applications")
    if _has_index(inspector, "api_key_applications", "ix_api_key_applications_user_id"):
        safe_drop_index("ix_api_key_applications_user_id", table_name="api_key_applications")

    with op.batch_alter_table("api_key_applications") as batch_op:
        if _has_column(inspector, "api_key_applications", "user_id"):
            batch_op.drop_column("user_id")
        if _has_column(inspector, "api_key_applications", "operator_account"):
            batch_op.drop_column("operator_account")
        if _has_column(inspector, "api_key_applications", "operator_name"):
            batch_op.drop_column("operator_name")
        if _has_column(inspector, "api_key_applications", "operator_email"):
            batch_op.drop_column("operator_email")
        if _has_column(inspector, "api_key_applications", "operator_department"):
            batch_op.drop_column("operator_department")
        if _has_column(inspector, "api_key_applications", "operator_sysid"):
            batch_op.drop_column("operator_sysid")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    with op.batch_alter_table("api_key_applications") as batch_op:
        if not _has_column(inspector, "api_key_applications", "user_id"):
            batch_op.add_column(sa.Column("user_id", sa.BigInteger(), nullable=True))
        if not _has_column(inspector, "api_key_applications", "operator_account"):
            batch_op.add_column(sa.Column("operator_account", sa.String(length=100), nullable=True))
        if not _has_column(inspector, "api_key_applications", "operator_name"):
            batch_op.add_column(sa.Column("operator_name", sa.String(length=100), nullable=True))
        if not _has_column(inspector, "api_key_applications", "operator_email"):
            batch_op.add_column(sa.Column("operator_email", sa.String(length=255), nullable=True))
        if not _has_column(inspector, "api_key_applications", "operator_department"):
            batch_op.add_column(sa.Column("operator_department", sa.String(length=100), nullable=True))
        if not _has_column(inspector, "api_key_applications", "operator_sysid"):
            batch_op.add_column(sa.Column("operator_sysid", sa.BigInteger(), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE api_key_applications
            SET
              user_id = sysid,
              operator_account = CASE
                  WHEN is_proxy_submission = TRUE THEN COALESCE(proxy_operator_account, account)
                  ELSE account
              END,
              operator_name = name,
              operator_email = email,
              operator_department = department,
              operator_sysid = CASE
                  WHEN is_proxy_submission = TRUE THEN sysid
                  ELSE sysid
              END
            """
        )
    )

    with op.batch_alter_table("api_key_applications") as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.BigInteger(), nullable=False)
        batch_op.alter_column("operator_account", existing_type=sa.String(length=100), nullable=False)
        batch_op.alter_column("operator_name", existing_type=sa.String(length=100), nullable=False)
        batch_op.alter_column("operator_email", existing_type=sa.String(length=255), nullable=False)
        batch_op.alter_column("operator_department", existing_type=sa.String(length=100), nullable=False)
        batch_op.alter_column("operator_sysid", existing_type=sa.BigInteger(), nullable=False)
        if _has_column(inspector, "api_key_applications", "proxy_operator_account"):
            batch_op.drop_column("proxy_operator_account")

    op.create_index("ix_api_key_applications_user_id", "api_key_applications", ["user_id"], unique=False)
    op.create_index("ix_api_key_applications_operator_sysid", "api_key_applications", ["operator_sysid"], unique=False)

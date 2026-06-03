"""add api key expiration notice history

Revision ID: 0033_api_key_exp_notices
Revises: 0032_rm_app_issue_cols
Create Date: 2026-06-03 16:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033_api_key_exp_notices"
down_revision: str | None = "0032_rm_app_issue_cols"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "api_key_expiration_notices" in set(inspector.get_table_names()):
        return

    op.create_table(
        "api_key_expiration_notices",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("key_id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("expires_at_snapshot", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notice_days_before", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("success_notice_days_before", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("notice_days_before in (30, 14, 7, 3, 1)", name="ck_api_key_exp_notices_days"),
        sa.CheckConstraint("status in ('sent', 'failed')", name="ck_api_key_exp_notices_status"),
        sa.ForeignKeyConstraint(["application_id"], ["api_key_applications.id"]),
        sa.ForeignKeyConstraint(["key_id"], ["api_keys.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "key_id",
            "expires_at_snapshot",
            "success_notice_days_before",
            name="uq_api_key_exp_notices_success_slot",
        ),
    )
    op.create_index(
        "ix_api_key_expiration_notices_key_id",
        "api_key_expiration_notices",
        ["key_id"],
        unique=False,
    )
    op.create_index(
        "ix_api_key_expiration_notices_application_id",
        "api_key_expiration_notices",
        ["application_id"],
        unique=False,
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "api_key_expiration_notices" not in set(inspector.get_table_names()):
        return

    indexes = {idx["name"] for idx in inspector.get_indexes("api_key_expiration_notices")}
    if "ix_api_key_expiration_notices_application_id" in indexes:
        op.drop_index("ix_api_key_expiration_notices_application_id", table_name="api_key_expiration_notices")
    if "ix_api_key_expiration_notices_key_id" in indexes:
        op.drop_index("ix_api_key_expiration_notices_key_id", table_name="api_key_expiration_notices")
    op.drop_table("api_key_expiration_notices")

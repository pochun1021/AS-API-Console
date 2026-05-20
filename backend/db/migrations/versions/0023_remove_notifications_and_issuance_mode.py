"""remove notifications table and selected issuance mode column

Revision ID: 0023_rm_notifications_issue_mode
Revises: 0022_operation_audit_logs
Create Date: 2026-05-20 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_rm_notifications_issue_mode"
down_revision: str | None = "0022_operation_audit_logs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in set(inspector.get_table_names())


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in set(inspector.get_table_names()):
        return False
    return column in {col["name"] for col in inspector.get_columns(table)}


def _index_exists(table: str, index: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in set(inspector.get_table_names()):
        return False
    return index in {idx["name"] for idx in inspector.get_indexes(table)}


def upgrade() -> None:
    if _column_exists("api_key_applications", "selected_issuance_mode"):
        op.drop_column("api_key_applications", "selected_issuance_mode")

    if _table_exists("notifications"):
        if _index_exists("notifications", "ix_notifications_sysid"):
            op.drop_index("ix_notifications_sysid", table_name="notifications")
        if _index_exists("notifications", "ix_notifications_user_id"):
            op.drop_index("ix_notifications_user_id", table_name="notifications")
        op.drop_table("notifications")


def downgrade() -> None:
    if not _table_exists("notifications"):
        op.create_table(
            "notifications",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("sysid", sa.BigInteger(), nullable=False),
            sa.Column("type", sa.String(length=50), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("email_delivery_status", sa.String(length=50), nullable=True),
            sa.Column("email_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_notifications_sysid", "notifications", ["sysid"], unique=False)

    if not _column_exists("api_key_applications", "selected_issuance_mode"):
        op.add_column("api_key_applications", sa.Column("selected_issuance_mode", sa.String(length=20), nullable=True))

"""rename notifications user_id column to sysid

Revision ID: 0016_notifications_sysid
Revises: 0015_drop_users_table
Create Date: 2026-05-18 23:40:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_notifications_sysid"
down_revision: str | None = "0015_drop_users_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "notifications" not in set(inspector.get_table_names()):
        return

    columns = {col["name"] for col in inspector.get_columns("notifications")}
    indexes = {idx["name"] for idx in inspector.get_indexes("notifications")}

    if "user_id" in columns and "sysid" not in columns:
        op.alter_column("notifications", "user_id", new_column_name="sysid", existing_type=sa.String(length=36))
        op.alter_column("notifications", "sysid", existing_type=sa.String(length=36), type_=sa.String(length=100))

    if "ix_notifications_user_id" in indexes:
        op.drop_index("ix_notifications_user_id", table_name="notifications")

    indexes = {idx["name"] for idx in sa.inspect(bind).get_indexes("notifications")}
    if "ix_notifications_sysid" not in indexes:
        op.create_index("ix_notifications_sysid", "notifications", ["sysid"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "notifications" not in set(inspector.get_table_names()):
        return

    columns = {col["name"] for col in inspector.get_columns("notifications")}
    indexes = {idx["name"] for idx in inspector.get_indexes("notifications")}

    if "ix_notifications_sysid" in indexes:
        op.drop_index("ix_notifications_sysid", table_name="notifications")

    if "sysid" in columns and "user_id" not in columns:
        op.alter_column("notifications", "sysid", new_column_name="user_id", existing_type=sa.String(length=100))
        op.alter_column("notifications", "user_id", existing_type=sa.String(length=100), type_=sa.String(length=36))

    indexes = {idx["name"] for idx in sa.inspect(bind).get_indexes("notifications")}
    if "ix_notifications_user_id" not in indexes:
        op.create_index("ix_notifications_user_id", "notifications", ["user_id"], unique=False)

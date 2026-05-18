"""drop users table after admin migration

Revision ID: 0015_drop_users_table
Revises: 0014_admins_detach_user_fks
Create Date: 2026-05-18 22:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_drop_users_table"
down_revision: str | None = "0014_admins_detach_user_fks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _drop_fk_to_users(table_name: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in set(inspector.get_table_names()):
        return
    for fk in inspector.get_foreign_keys(table_name):
        fk_name = fk.get("name")
        if fk.get("referred_table") == "users" and fk_name:
            op.drop_constraint(fk_name, table_name, type_="foreignkey")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "users" not in existing_tables:
        return

    _drop_fk_to_users("api_key_applications")
    _drop_fk_to_users("notifications")

    existing_indexes = {idx["name"] for idx in inspector.get_indexes("users")}
    if "ix_users_email" in existing_indexes:
        op.drop_index("ix_users_email", table_name="users")
    if "ix_users_account" in existing_indexes:
        op.drop_index("ix_users_account", table_name="users")
    op.drop_table("users")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "users" in existing_tables:
        return

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("preferred_locale", sa.String(length=10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role in ('user', 'admin')", name="ck_users_role"),
        sa.CheckConstraint("status in ('active', 'inactive')", name="ck_users_status"),
        sa.CheckConstraint("preferred_locale in ('zh-TW', 'en')", name="ck_users_preferred_locale"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_account", "users", ["account"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

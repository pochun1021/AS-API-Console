"""create core tables for mvp

Revision ID: 0002_create_core_tables
Revises: 0001_init_empty
Create Date: 2026-05-06 00:30:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from db.migrations.helpers import safe_drop_index, safe_drop_table

revision: str = "0002_create_core_tables"
down_revision: str | None = "0001_init_empty"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role in ('user', 'admin')", name="ck_users_role"),
        sa.CheckConstraint("status in ('active', 'inactive')", name="ck_users_status"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_account", "users", ["account"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "api_key_whitelist",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=100), nullable=False),
        sa.Column("updated_by", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status in ('active', 'inactive')", name="ck_whitelist_status"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_key_whitelist_email", "api_key_whitelist", ["email"], unique=True)

    op.create_table(
        "api_key_applications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account", sa.String(length=100), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("department", sa.String(length=100), nullable=False),
        sa.Column("application_date", sa.Date(), nullable=False),
        sa.Column("duration_months", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sysid", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("duration_months in (1, 6, 12)", name="ck_applications_duration_months"),
        sa.CheckConstraint("status in ('active', 'revoked', 'expired')", name="ck_applications_status"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_key_applications_email", "api_key_applications", ["email"], unique=False)
    op.create_index("ix_api_key_applications_sysid", "api_key_applications", ["sysid"], unique=False)
    op.create_index("ix_api_key_applications_user_id", "api_key_applications", ["user_id"], unique=False)

    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("key_hash", sa.String(length=255), nullable=False),
        sa.Column("key_prefix", sa.String(length=10), nullable=False, server_default="AS-"),
        sa.Column("length", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("security_level", sa.String(length=20), nullable=False, server_default="high"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status in ('active', 'revoked', 'expired')", name="ck_api_keys_status"),
        sa.CheckConstraint("length = 30", name="ck_api_keys_length"),
        sa.CheckConstraint("security_level = 'high'", name="ck_api_keys_security_level"),
        sa.ForeignKeyConstraint(["application_id"], ["api_key_applications.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id"),
    )
    op.create_index("ix_api_keys_application_id", "api_keys", ["application_id"], unique=True)


def downgrade() -> None:
    safe_drop_index("ix_api_keys_application_id", table_name="api_keys")
    safe_drop_table("api_keys")

    safe_drop_index("ix_api_key_applications_user_id", table_name="api_key_applications")
    safe_drop_index("ix_api_key_applications_sysid", table_name="api_key_applications")
    safe_drop_index("ix_api_key_applications_email", table_name="api_key_applications")
    safe_drop_table("api_key_applications")

    safe_drop_index("ix_api_key_whitelist_email", table_name="api_key_whitelist")
    safe_drop_table("api_key_whitelist")

    safe_drop_index("ix_users_email", table_name="users")
    safe_drop_index("ix_users_account", table_name="users")
    safe_drop_table("users")

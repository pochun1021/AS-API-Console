"""create admins table and detach user foreign keys

Revision ID: 0014_admins_detach_user_fks
Revises: 0013_rm_limit_strategy_templates
Create Date: 2026-05-18 20:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_admins_detach_user_fks"
down_revision: str | None = "0013_rm_limit_strategy_templates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _drop_fk_to_users(table_name: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if table_name not in existing_tables:
        return

    for fk in inspector.get_foreign_keys(table_name):
        referred_table = fk.get("referred_table")
        constrained_cols = fk.get("constrained_columns") or []
        fk_name = fk.get("name")
        if referred_table == "users" and "user_id" in constrained_cols and fk_name:
            op.drop_constraint(fk_name, table_name, type_="foreignkey")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "admins" not in existing_tables:
        op.create_table(
            "admins",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("account", sa.String(length=100), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("department", sa.String(length=100), nullable=True),
            sa.Column("sysid", sa.String(length=100), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
            sa.Column("created_by", sa.String(length=100), nullable=False),
            sa.Column("updated_by", sa.String(length=100), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("status in ('active', 'inactive')", name="ck_admins_status"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_admins_account", "admins", ["account"], unique=True)
        op.create_index("ix_admins_email", "admins", ["email"], unique=True)
        op.create_index("ix_admins_sysid", "admins", ["sysid"], unique=True)

    existing_tables = set(inspector.get_table_names())
    if "users" in existing_tables and "admins" in existing_tables:
        op.execute(
            """
            INSERT INTO admins (id, account, email, name, department, sysid, status, created_by, updated_by, created_at, updated_at)
            SELECT
                u.id,
                u.account,
                LOWER(u.email),
                u.name,
                NULL AS department,
                u.id AS sysid,
                CASE WHEN u.status = 'inactive' THEN 'inactive' ELSE 'active' END AS status,
                'migration_0014',
                'migration_0014',
                u.created_at,
                u.updated_at
            FROM users u
            WHERE u.role = 'admin'
            ON DUPLICATE KEY UPDATE
                account = VALUES(account),
                email = VALUES(email),
                name = VALUES(name),
                status = VALUES(status),
                updated_by = VALUES(updated_by),
                updated_at = VALUES(updated_at)
            """
        )

    _drop_fk_to_users("api_key_applications")
    _drop_fk_to_users("notifications")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "admins" in existing_tables:
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("admins")}
        if "ix_admins_sysid" in existing_indexes:
            op.drop_index("ix_admins_sysid", table_name="admins")
        if "ix_admins_email" in existing_indexes:
            op.drop_index("ix_admins_email", table_name="admins")
        if "ix_admins_account" in existing_indexes:
            op.drop_index("ix_admins_account", table_name="admins")
        op.drop_table("admins")

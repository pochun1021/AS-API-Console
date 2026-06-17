"""add auth_audit_logs table

Revision ID: 0017_auth_audit_logs
Revises: 0016_notifications_sysid
Create Date: 2026-05-19 00:35:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from db.migrations.helpers import safe_drop_index, safe_drop_table

revision: str = "0017_auth_audit_logs"
down_revision: str | None = "0016_notifications_sysid"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_audit_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("request_id", sa.String(length=100), nullable=False),
        sa.Column("result", sa.String(length=20), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("account", sa.String(length=100), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("department", sa.String(length=100), nullable=True),
        sa.Column("sysid", sa.String(length=100), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_audit_logs_request_id", "auth_audit_logs", ["request_id"], unique=False)
    op.create_index("ix_auth_audit_logs_result", "auth_audit_logs", ["result"], unique=False)
    op.create_index("ix_auth_audit_logs_sysid", "auth_audit_logs", ["sysid"], unique=False)


def downgrade() -> None:
    safe_drop_index("ix_auth_audit_logs_sysid", table_name="auth_audit_logs")
    safe_drop_index("ix_auth_audit_logs_result", table_name="auth_audit_logs")
    safe_drop_index("ix_auth_audit_logs_request_id", table_name="auth_audit_logs")
    safe_drop_table("auth_audit_logs")

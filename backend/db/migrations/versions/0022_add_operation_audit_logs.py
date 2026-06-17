"""add operation_audit_logs table

Revision ID: 0022_operation_audit_logs
Revises: 0021_sysid_bigint
Create Date: 2026-05-19 12:20:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from db.migrations.helpers import safe_drop_index, safe_drop_table

revision: str = "0022_operation_audit_logs"
down_revision: str | None = "0021_sysid_bigint"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operation_audit_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("result", sa.String(length=20), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("actor_sysid", sa.BigInteger(), nullable=True),
        sa.Column("actor_account", sa.String(length=100), nullable=True),
        sa.Column("actor_role", sa.String(length=20), nullable=True),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("target_id", sa.String(length=100), nullable=True),
        sa.Column("request_id", sa.String(length=100), nullable=False),
        sa.Column("source_ip", sa.String(length=100), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_operation_audit_logs_actor_sysid", "operation_audit_logs", ["actor_sysid"], unique=False)
    op.create_index("ix_operation_audit_logs_created_at", "operation_audit_logs", ["created_at"], unique=False)
    op.create_index("ix_operation_audit_logs_event_type", "operation_audit_logs", ["event_type"], unique=False)
    op.create_index("ix_operation_audit_logs_request_id", "operation_audit_logs", ["request_id"], unique=False)
    op.create_index("ix_operation_audit_logs_result", "operation_audit_logs", ["result"], unique=False)


def downgrade() -> None:
    safe_drop_index("ix_operation_audit_logs_result", table_name="operation_audit_logs")
    safe_drop_index("ix_operation_audit_logs_request_id", table_name="operation_audit_logs")
    safe_drop_index("ix_operation_audit_logs_event_type", table_name="operation_audit_logs")
    safe_drop_index("ix_operation_audit_logs_created_at", table_name="operation_audit_logs")
    safe_drop_index("ix_operation_audit_logs_actor_sysid", table_name="operation_audit_logs")
    safe_drop_table("operation_audit_logs")

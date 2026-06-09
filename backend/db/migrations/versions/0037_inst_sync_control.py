"""add institute sync control

Revision ID: 0037_inst_sync_control
Revises: 0036_max_parallel_req
Create Date: 2026-06-09 00:00:00
"""

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision: str = "0037_inst_sync_control"
down_revision: str | None = "0036_max_parallel_req"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONTROL_ROW_ID = 1


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in set(inspector.get_table_names())


def upgrade() -> None:
    if not _table_exists("institute_sync_control"):
        op.create_table(
            "institute_sync_control",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("last_result", sa.String(length=64), nullable=True),
            sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("status in ('idle', 'running')", name="ck_institute_sync_control_status"),
            sa.PrimaryKeyConstraint("id"),
        )

    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    existing = bind.execute(
        sa.text("SELECT id FROM institute_sync_control WHERE id = :id"),
        {"id": CONTROL_ROW_ID},
    ).first()
    if existing is None:
        bind.execute(
            sa.text(
                """
                INSERT INTO institute_sync_control
                    (id, status, last_result, last_started_at, last_finished_at, cooldown_until, created_at, updated_at)
                VALUES
                    (:id, :status, :last_result, :last_started_at, :last_finished_at, :cooldown_until, :created_at, :updated_at)
                """
            ),
            {
                "id": CONTROL_ROW_ID,
                "status": "idle",
                "last_result": None,
                "last_started_at": None,
                "last_finished_at": None,
                "cooldown_until": None,
                "created_at": now,
                "updated_at": now,
            },
        )


def downgrade() -> None:
    if _table_exists("institute_sync_control"):
        op.drop_table("institute_sync_control")

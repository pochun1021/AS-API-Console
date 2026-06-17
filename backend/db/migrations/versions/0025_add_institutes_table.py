"""add institutes table

Revision ID: 0025_institutes_table
Revises: 0024_api_key_renew_link
Create Date: 2026-05-22 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from db.migrations.helpers import safe_drop_table

revision: str = "0025_institutes_table"
down_revision: str | None = "0024_api_key_renew_link"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in set(inspector.get_table_names())


def upgrade() -> None:
    if _table_exists("institutes"):
        return

    op.create_table(
        "institutes",
        sa.Column("inst_code", sa.String(length=20), nullable=False),
        sa.Column("inst_name", sa.String(length=255), nullable=False),
        sa.Column("abb_inst_name", sa.String(length=255), nullable=True),
        sa.Column("einst_name", sa.String(length=255), nullable=True),
        sa.Column("division", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status in ('active', 'inactive')", name="ck_institutes_status"),
        sa.PrimaryKeyConstraint("inst_code"),
    )


def downgrade() -> None:
    if not _table_exists("institutes"):
        return
    safe_drop_table("institutes")

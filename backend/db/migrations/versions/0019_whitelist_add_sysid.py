"""add sysid column to whitelist and switch uniqueness

Revision ID: 0019_whitelist_sysid
Revises: 0018_user_preferences
Create Date: 2026-05-18 16:25:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_whitelist_sysid"
down_revision: str | None = "0018_user_preferences"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("api_key_whitelist", sa.Column("sysid", sa.String(length=100), nullable=True))
    op.execute("UPDATE api_key_whitelist SET sysid = email WHERE sysid IS NULL")
    with op.batch_alter_table("api_key_whitelist") as batch_op:
        batch_op.alter_column("sysid", existing_type=sa.String(length=100), nullable=False)
        batch_op.alter_column("email", existing_type=sa.String(length=255), nullable=True)
    op.create_index("ix_api_key_whitelist_sysid", "api_key_whitelist", ["sysid"], unique=True)
    op.drop_index("ix_api_key_whitelist_email", table_name="api_key_whitelist")


def downgrade() -> None:
    op.create_index("ix_api_key_whitelist_email", "api_key_whitelist", ["email"], unique=True)
    op.drop_index("ix_api_key_whitelist_sysid", table_name="api_key_whitelist")
    with op.batch_alter_table("api_key_whitelist") as batch_op:
        batch_op.alter_column("email", existing_type=sa.String(length=255), nullable=False)
    op.drop_column("api_key_whitelist", "sysid")

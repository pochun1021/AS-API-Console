"""add account and name to whitelist

Revision ID: 0029_whitelist_add_account_name
Revises: 0028_api_key_exp_notice_sent_at
Create Date: 2026-06-01 15:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029_whitelist_add_account_name"
down_revision: str | None = "0028_api_key_exp_notice_sent_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("api_key_whitelist")}
    if "account" not in columns:
        op.add_column("api_key_whitelist", sa.Column("account", sa.String(length=100), nullable=True))
    if "name" not in columns:
        op.add_column("api_key_whitelist", sa.Column("name", sa.String(length=100), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("api_key_whitelist")}
    if "name" in columns:
        op.drop_column("api_key_whitelist", "name")
    if "account" in columns:
        op.drop_column("api_key_whitelist", "account")

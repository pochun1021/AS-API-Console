"""add api key expiration reminder sent timestamp

Revision ID: 0028_api_key_exp_notice_sent_at
Revises: 0027_backfill_admins_current
Create Date: 2026-05-26 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028_api_key_exp_notice_sent_at"
down_revision: str | None = "0027_backfill_admins_current"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("api_keys")}
    if "expiration_notice_sent_at" in columns:
        return
    op.add_column("api_keys", sa.Column("expiration_notice_sent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("api_keys")}
    if "expiration_notice_sent_at" not in columns:
        return
    op.drop_column("api_keys", "expiration_notice_sent_at")

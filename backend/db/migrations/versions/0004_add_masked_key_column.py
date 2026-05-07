"""add masked_key column to api_keys

Revision ID: 0004_add_masked_key_column
Revises: 0003_add_users_preferred_locale
Create Date: 2026-05-07 16:40:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_add_masked_key_column"
down_revision: str | None = "0003_add_users_preferred_locale"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("api_keys")}
    if "masked_key" not in existing_columns:
        op.add_column("api_keys", sa.Column("masked_key", sa.String(length=32), nullable=True))
    op.execute(sa.text("UPDATE api_keys SET masked_key = 'AS-xxxx****xxxx' WHERE masked_key IS NULL"))
    op.alter_column("api_keys", "masked_key", existing_type=sa.String(length=32), nullable=False)


def downgrade() -> None:
    op.drop_column("api_keys", "masked_key")

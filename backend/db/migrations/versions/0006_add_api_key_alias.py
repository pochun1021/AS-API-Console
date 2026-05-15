"""add api key alias column

Revision ID: 0006_add_api_key_alias
Revises: 0005_add_encrypted_key_material
Create Date: 2026-05-15 16:20:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_add_api_key_alias"
down_revision: str | None = "0005_add_encrypted_key_material"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("api_keys")}
    if "key_alias" not in existing_columns:
        op.add_column("api_keys", sa.Column("key_alias", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("api_keys", "key_alias")

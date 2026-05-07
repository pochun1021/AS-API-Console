"""add encrypted key material columns

Revision ID: 0005_add_encrypted_key_material
Revises: 0004_add_masked_key_column
Create Date: 2026-05-07 19:20:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_add_encrypted_key_material"
down_revision: str | None = "0004_add_masked_key_column"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("api_keys")}
    if "key_ciphertext" not in existing_columns:
        op.add_column("api_keys", sa.Column("key_ciphertext", sa.Text(), nullable=True))
    if "key_kek_version" not in existing_columns:
        op.add_column("api_keys", sa.Column("key_kek_version", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("api_keys", "key_kek_version")
    op.drop_column("api_keys", "key_ciphertext")

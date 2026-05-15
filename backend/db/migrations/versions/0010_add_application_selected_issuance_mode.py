"""add selected issuance mode for pending review

Revision ID: 0010_application_selected_mode
Revises: 0009_ls_global_cfg
Create Date: 2026-05-15 22:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_application_selected_mode"
down_revision: str | None = "0009_ls_global_cfg"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("api_key_applications")}

    if "selected_issuance_mode" not in existing_columns:
        op.add_column("api_key_applications", sa.Column("selected_issuance_mode", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("api_key_applications", "selected_issuance_mode")

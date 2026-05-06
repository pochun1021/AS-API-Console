"""init empty migration for skeleton

Revision ID: 0001_init_empty
Revises:
Create Date: 2026-05-06 00:00:00

"""

from collections.abc import Sequence

revision: str = "0001_init_empty"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

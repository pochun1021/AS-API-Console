"""add users preferred locale

Revision ID: 0003_add_users_preferred_locale
Revises: 0002_create_core_tables
Create Date: 2026-05-07 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from db.migrations.helpers import safe_drop_constraint


# revision identifiers, used by Alembic.
revision: str = "0003_add_users_preferred_locale"
down_revision: Union[str, Sequence[str], None] = "0002_create_core_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("preferred_locale", sa.String(length=10), nullable=True))
    op.create_check_constraint(
        "ck_users_preferred_locale",
        "users",
        "preferred_locale in ('zh-TW', 'en') or preferred_locale is null",
    )


def downgrade() -> None:
    safe_drop_constraint("ck_users_preferred_locale", "users", type_="check")
    op.drop_column("users", "preferred_locale")

"""change admins.id to bigint and drop redundant sysid

Revision ID: 0026_admins_id_bigint
Revises: 0025_institutes_table
Create Date: 2026-05-22 22:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from db.migrations.helpers import safe_drop_index

revision: str = "0026_admins_id_bigint"
down_revision: str | None = "0025_institutes_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ensure_admin_ids_numeric_or_raise() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id FROM admins WHERE id IS NOT NULL")).fetchall()
    invalid = [str(row[0]) for row in rows if not str(row[0]).isdigit()]
    if invalid:
        sample = ", ".join(invalid[:5])
        raise RuntimeError(
            f"Cannot migrate admins.id to BIGINT. Non-numeric ids found: {sample}"
        )


def upgrade() -> None:
    _ensure_admin_ids_numeric_or_raise()
    safe_drop_index("ix_admins_sysid", table_name="admins")
    op.drop_column("admins", "sysid")
    with op.batch_alter_table("admins", recreate="always") as batch_op:
        batch_op.alter_column("id", existing_type=sa.String(length=36), type_=sa.BigInteger(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("admins", recreate="always") as batch_op:
        batch_op.alter_column("id", existing_type=sa.BigInteger(), type_=sa.String(length=36), nullable=False)
    op.add_column("admins", sa.Column("sysid", sa.BigInteger(), nullable=True))
    op.execute("UPDATE admins SET sysid = id WHERE sysid IS NULL")
    with op.batch_alter_table("admins", recreate="always") as batch_op:
        batch_op.alter_column("sysid", existing_type=sa.BigInteger(), nullable=False)
    op.create_index("ix_admins_sysid", "admins", ["sysid"], unique=True)

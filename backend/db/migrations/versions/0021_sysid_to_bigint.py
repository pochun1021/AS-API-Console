"""change sysid columns to bigint and enforce numeric data

Revision ID: 0021_sysid_bigint
Revises: 0020_application_operator
Create Date: 2026-05-19
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0021_sysid_bigint"
down_revision: str | None = "0020_application_operator"
branch_labels = None
depends_on = None


def _ensure_numeric_or_raise(table: str, column: str) -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        query = sa.text(
            f"SELECT 1 FROM {table} WHERE {column} IS NOT NULL "
            f"AND (TRIM({column}) = '' OR {column} GLOB '*[^0-9]*') LIMIT 1"
        )
    elif dialect == "postgresql":
        query = sa.text(
            f"SELECT 1 FROM {table} WHERE {column} IS NOT NULL "
            f"AND {column} !~ '^[0-9]+$' LIMIT 1"
        )
    else:
        query = sa.text(
            f"SELECT 1 FROM {table} WHERE {column} IS NOT NULL "
            f"AND NOT ({column} REGEXP '^[0-9]+$') LIMIT 1"
        )
    exists = bind.execute(query).first()
    if exists:
        raise RuntimeError(f"non-numeric {table}.{column} detected; abort migration")


def upgrade() -> None:
    _ensure_numeric_or_raise("admins", "sysid")
    _ensure_numeric_or_raise("api_key_whitelist", "sysid")
    _ensure_numeric_or_raise("api_key_applications", "user_id")
    _ensure_numeric_or_raise("api_key_applications", "sysid")
    _ensure_numeric_or_raise("api_key_applications", "operator_sysid")
    _ensure_numeric_or_raise("notifications", "sysid")
    _ensure_numeric_or_raise("user_preferences", "sysid")
    _ensure_numeric_or_raise("auth_audit_logs", "sysid")

    with op.batch_alter_table("admins") as batch_op:
        batch_op.alter_column("sysid", existing_type=sa.String(length=100), type_=sa.BigInteger(), nullable=False)

    with op.batch_alter_table("api_key_whitelist") as batch_op:
        batch_op.alter_column("sysid", existing_type=sa.String(length=100), type_=sa.BigInteger(), nullable=False)

    with op.batch_alter_table("api_key_applications") as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.String(length=36), type_=sa.BigInteger(), nullable=False)
        batch_op.alter_column("sysid", existing_type=sa.String(length=100), type_=sa.BigInteger(), nullable=False)
        batch_op.alter_column("operator_sysid", existing_type=sa.String(length=100), type_=sa.BigInteger(), nullable=False)

    with op.batch_alter_table("notifications") as batch_op:
        batch_op.alter_column("sysid", existing_type=sa.String(length=100), type_=sa.BigInteger(), nullable=False)

    with op.batch_alter_table("user_preferences") as batch_op:
        batch_op.alter_column("sysid", existing_type=sa.String(length=100), type_=sa.BigInteger(), nullable=False)

    with op.batch_alter_table("auth_audit_logs") as batch_op:
        batch_op.alter_column("sysid", existing_type=sa.String(length=100), type_=sa.BigInteger(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("auth_audit_logs") as batch_op:
        batch_op.alter_column("sysid", existing_type=sa.BigInteger(), type_=sa.String(length=100), nullable=True)

    with op.batch_alter_table("user_preferences") as batch_op:
        batch_op.alter_column("sysid", existing_type=sa.BigInteger(), type_=sa.String(length=100), nullable=False)

    with op.batch_alter_table("notifications") as batch_op:
        batch_op.alter_column("sysid", existing_type=sa.BigInteger(), type_=sa.String(length=100), nullable=False)

    with op.batch_alter_table("api_key_applications") as batch_op:
        batch_op.alter_column("operator_sysid", existing_type=sa.BigInteger(), type_=sa.String(length=100), nullable=False)
        batch_op.alter_column("sysid", existing_type=sa.BigInteger(), type_=sa.String(length=100), nullable=False)
        batch_op.alter_column("user_id", existing_type=sa.BigInteger(), type_=sa.String(length=36), nullable=False)

    with op.batch_alter_table("api_key_whitelist") as batch_op:
        batch_op.alter_column("sysid", existing_type=sa.BigInteger(), type_=sa.String(length=100), nullable=False)

    with op.batch_alter_table("admins") as batch_op:
        batch_op.alter_column("sysid", existing_type=sa.BigInteger(), type_=sa.String(length=100), nullable=False)

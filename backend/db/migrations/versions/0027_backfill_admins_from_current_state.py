"""upsert fixed admin row during deployment

Revision ID: 0027_backfill_admins_current
Revises: 0026_admins_id_bigint
Create Date: 2026-05-25 10:20:00
"""

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision: str = "0027_backfill_admins_current"
down_revision: str | None = "0026_admins_id_bigint"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MIGRATION_ACTOR = "migration_0027"
TARGET_ADMIN_ID = 5019561
TARGET_ADMIN_ACCOUNT = "pochen"
TARGET_ADMIN_EMAIL = "pochen@as.edu.tw"
TARGET_ADMIN_NAME = "阮柏鈞"
TARGET_ADMIN_DEPARTMENT = "24"
TARGET_ADMIN_STATUS = "active"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "admins" not in existing_tables:
        return

    now = datetime.now(timezone.utc)
    existing = bind.execute(
        sa.text(
            """
            SELECT id
            FROM admins
            WHERE id = :id
            """
        ),
        {"id": TARGET_ADMIN_ID},
    ).first()

    if existing:
        bind.execute(
            sa.text(
                """
                UPDATE admins
                SET account = :account,
                    email = :email,
                    name = :name,
                    department = :department,
                    status = :status,
                    updated_by = :updated_by,
                    updated_at = :updated_at
                WHERE id = :id
                """
            ),
            {
                "id": TARGET_ADMIN_ID,
                "account": TARGET_ADMIN_ACCOUNT,
                "email": TARGET_ADMIN_EMAIL.lower(),
                "name": TARGET_ADMIN_NAME,
                "department": TARGET_ADMIN_DEPARTMENT,
                "status": TARGET_ADMIN_STATUS,
                "updated_by": MIGRATION_ACTOR,
                "updated_at": now,
            },
        )
        return

    bind.execute(
        sa.text(
            """
            INSERT INTO admins (id, account, email, name, department, status, created_by, updated_by, created_at, updated_at)
            VALUES (:id, :account, :email, :name, :department, :status, :created_by, :updated_by, :created_at, :updated_at)
            """
        ),
        {
            "id": TARGET_ADMIN_ID,
            "account": TARGET_ADMIN_ACCOUNT,
            "email": TARGET_ADMIN_EMAIL.lower(),
            "name": TARGET_ADMIN_NAME,
            "department": TARGET_ADMIN_DEPARTMENT,
            "status": TARGET_ADMIN_STATUS,
            "created_by": MIGRATION_ACTOR,
            "updated_by": MIGRATION_ACTOR,
            "created_at": now,
            "updated_at": now,
        },
    )


def downgrade() -> None:
    # Irreversible data backfill migration.
    pass

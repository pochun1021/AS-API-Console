"""add max_parallel_requests to limit strategy and applications

Revision ID: 0036_max_parallel_req
Revises: 0035_app_duration_positive
Create Date: 2026-06-08 10:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0036_max_parallel_req"
down_revision: str | None = "0035_app_duration_positive"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("limit_strategy_config") as batch_op:
        batch_op.add_column(
            sa.Column("max_parallel_requests", sa.Integer(), nullable=False, server_default="0")
        )

    with op.batch_alter_table("api_key_applications") as batch_op:
        batch_op.add_column(sa.Column("max_parallel_requests", sa.Integer(), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE limit_strategy_config
            SET max_parallel_requests = 0
            WHERE max_parallel_requests IS NULL
            """
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("api_key_applications") as batch_op:
        batch_op.drop_column("max_parallel_requests")

    with op.batch_alter_table("limit_strategy_config") as batch_op:
        batch_op.drop_column("max_parallel_requests")

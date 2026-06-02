"""remove per-application issuance state columns

Revision ID: 0032_rm_app_issue_cols
Revises: 0031_app_proxy_operator
Create Date: 2026-06-02 14:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032_rm_app_issue_cols"
down_revision: str | None = "0031_app_proxy_operator"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(inspector: sa.Inspector, table: str, column: str) -> bool:
    return column in {item["name"] for item in inspector.get_columns(table)}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    with op.batch_alter_table("api_key_applications") as batch_op:
        if _has_column(inspector, "api_key_applications", "limit_strategy"):
            batch_op.drop_column("limit_strategy")
        if _has_column(inspector, "api_key_applications", "issuance_status"):
            batch_op.drop_column("issuance_status")
        if _has_column(inspector, "api_key_applications", "pending_issued_at"):
            batch_op.drop_column("pending_issued_at")


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    with op.batch_alter_table("api_key_applications") as batch_op:
        if not _has_column(inspector, "api_key_applications", "limit_strategy"):
            batch_op.add_column(sa.Column("limit_strategy", sa.String(length=20), nullable=True))
        if not _has_column(inspector, "api_key_applications", "issuance_status"):
            batch_op.add_column(sa.Column("issuance_status", sa.String(length=20), nullable=True))
        if not _has_column(inspector, "api_key_applications", "pending_issued_at"):
            batch_op.add_column(sa.Column("pending_issued_at", sa.DateTime(timezone=True), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE api_key_applications
            SET
              limit_strategy = COALESCE(limit_strategy, 'budget+rate_limit'),
              issuance_status = COALESCE(issuance_status, 'issued'),
              pending_issued_at = COALESCE(pending_issued_at, issued_at)
            """
        )
    )

    with op.batch_alter_table("api_key_applications") as batch_op:
        batch_op.alter_column("limit_strategy", existing_type=sa.String(length=20), nullable=False)
        batch_op.alter_column("issuance_status", existing_type=sa.String(length=20), nullable=False)

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Institute(Base):
    __tablename__ = "institutes"
    __table_args__ = (
        CheckConstraint("status in ('active', 'inactive')", name="ck_institutes_status"),
    )

    inst_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    inst_name: Mapped[str] = mapped_column(String(255), nullable=False)
    abb_inst_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    einst_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    division: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

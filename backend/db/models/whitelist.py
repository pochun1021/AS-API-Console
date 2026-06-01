from datetime import datetime, timezone

from sqlalchemy import BigInteger, CheckConstraint, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class ApiKeyWhitelist(Base):
    __tablename__ = "api_key_whitelist"
    __table_args__ = (
        CheckConstraint("status in ('active', 'inactive')", name="ck_whitelist_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    sysid: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    account: Mapped[str | None] = mapped_column(String(100), nullable=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

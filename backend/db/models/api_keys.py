from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class ApiKey(Base):
    __tablename__ = "api_keys"
    __table_args__ = (
        CheckConstraint("status in ('active', 'revoked', 'expired')", name="ck_api_keys_status"),
        CheckConstraint("length = 30", name="ck_api_keys_length"),
        CheckConstraint("security_level = 'high'", name="ck_api_keys_security_level"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    application_id: Mapped[str] = mapped_column(
        ForeignKey("api_key_applications.id"), nullable=False, unique=True, index=True
    )
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(10), default="AS-", nullable=False)
    masked_key: Mapped[str] = mapped_column(String(32), nullable=False)
    key_ciphertext: Mapped[str | None] = mapped_column(Text(), nullable=True)
    key_kek_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    length: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    security_level: Mapped[str] = mapped_column(String(20), default="high", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    application: Mapped["ApiKeyApplication"] = relationship(back_populates="api_key")

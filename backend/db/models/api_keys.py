from datetime import datetime, timezone

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text
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
    renewed_to_key_id: Mapped[str | None] = mapped_column(ForeignKey("api_keys.id"), nullable=True, index=True)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(10), default="AS-", nullable=False)
    masked_key: Mapped[str] = mapped_column(String(32), nullable=False)
    key_alias: Mapped[str | None] = mapped_column(String(100), nullable=True)
    key_ciphertext: Mapped[str | None] = mapped_column(Text(), nullable=True)
    key_kek_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    length: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    security_level: Mapped[str] = mapped_column(String(20), default="high", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    expiration_notice_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    usage_spend: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    usage_prompt_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    usage_completion_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    usage_total_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    usage_budget_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    usage_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    application: Mapped["ApiKeyApplication"] = relationship(back_populates="api_key")
    usage_snapshots: Mapped[list["ApiKeyUsageSnapshot"]] = relationship(back_populates="api_key")

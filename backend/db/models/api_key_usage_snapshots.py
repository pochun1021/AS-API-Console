from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class ApiKeyUsageSnapshot(Base):
    __tablename__ = "api_key_usage_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "api_key_id",
            "bucket_granularity",
            "bucket_start_utc",
            name="uq_api_key_usage_snapshots_bucket",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    api_key_id: Mapped[str] = mapped_column(ForeignKey("api_keys.id"), nullable=False, index=True)
    bucket_granularity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bucket_start_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bucket_end_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    spend: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default=text("0"))
    completion_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default=text("0"))
    total_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default=text("0"))
    budget_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )

    api_key: Mapped["ApiKey"] = relationship(back_populates="usage_snapshots")

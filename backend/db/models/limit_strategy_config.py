from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class LimitStrategyConfig(Base):
    __tablename__ = "limit_strategy_config"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    budget_max_budget: Mapped[str] = mapped_column(String(100), nullable=False, default="1000")
    budget_duration: Mapped[str] = mapped_column(String(20), nullable=False, default="monthly")
    rate_limit_tpm: Mapped[int] = mapped_column(Integer, nullable=False, default=10000)
    rate_limit_rpm: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    max_parallel_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

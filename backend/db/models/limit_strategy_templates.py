from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class LimitStrategyTemplate(Base):
    __tablename__ = "limit_strategy_templates"
    __table_args__ = (
        CheckConstraint("strategy_type in ('budget', 'rate_limit')", name="ck_limit_strategy_templates_type"),
        CheckConstraint("status in ('active', 'inactive')", name="ck_limit_strategy_templates_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    strategy_type: Mapped[str] = mapped_column(String(20), nullable=False)
    max_budget: Mapped[str | None] = mapped_column(String(100), nullable=True)
    budget_duration: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tpm_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rpm_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
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

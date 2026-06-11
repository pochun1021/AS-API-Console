from datetime import date, datetime, timezone

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class ApiKeyApplication(Base):
    __tablename__ = "api_key_applications"
    __table_args__ = (
        CheckConstraint("duration_months > 0", name="ck_applications_duration_months"),
        CheckConstraint("original_duration_months > 0", name="ck_applications_original_duration_months"),
        CheckConstraint("status in ('active', 'revoked', 'expired')", name="ck_applications_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    application_date: Mapped[date] = mapped_column(Date, nullable=False)
    duration_months: Mapped[int] = mapped_column(Integer, nullable=False)
    original_duration_months: Mapped[int] = mapped_column(Integer, nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    max_budget: Mapped[str | None] = mapped_column(String(100), nullable=True)
    budget_duration: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tpm_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rpm_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_parallel_requests: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sysid: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    is_proxy_submission: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    proxy_operator_account: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    api_key: Mapped["ApiKey"] = relationship(back_populates="application", uselist=False)

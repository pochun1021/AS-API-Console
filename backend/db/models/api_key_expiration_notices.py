from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class ApiKeyExpirationNotice(Base):
    __tablename__ = "api_key_expiration_notices"
    __table_args__ = (
        CheckConstraint("notice_days_before in (30, 14, 7, 3, 1)", name="ck_api_key_exp_notices_days"),
        CheckConstraint("status in ('sent', 'failed')", name="ck_api_key_exp_notices_status"),
        UniqueConstraint(
            "key_id",
            "expires_at_snapshot",
            "success_notice_days_before",
            name="uq_api_key_exp_notices_success_slot",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    key_id: Mapped[str] = mapped_column(ForeignKey("api_keys.id"), nullable=False, index=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("api_key_applications.id"), nullable=False, index=True)
    expires_at_snapshot: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notice_days_before: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    success_notice_days_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

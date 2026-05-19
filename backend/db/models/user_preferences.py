from datetime import datetime, timezone

from sqlalchemy import BigInteger, CheckConstraint, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class UserPreference(Base):
    __tablename__ = "user_preferences"
    __table_args__ = (CheckConstraint("preferred_locale in ('zh-TW', 'en')", name="ck_user_preferences_locale"),)

    sysid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    preferred_locale: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

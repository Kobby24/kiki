import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    phone_number: Mapped[str] = mapped_column(
        String(20), unique=True, index=True, nullable=False
    )
    # Set once the phone number has been proven via OTP; used to gate
    # login and to record when the account became trustworthy.
    phone_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    preferred_language: Mapped[str] = mapped_column(String(10), default="tw")
    accessibility_preferences: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    cashouts = relationship("CashoutRequest", back_populates="user")

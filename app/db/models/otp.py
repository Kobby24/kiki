import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, Enum, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class OtpPurpose(str, enum.Enum):
    REGISTRATION = "registration"
    LOGIN = "login"


class OtpCode(Base):
    """A single one-time-passcode issued for a phone number.

    Codes are never stored in plaintext: `code_hash` is an HMAC of the code,
    the phone number, and the purpose, so a stolen row cannot be replayed
    against another phone number or flow. Each row tracks its own attempt
    count and expiry so verification, lockout, and resend/rate limiting can
    all be enforced from this table alone.
    """

    __tablename__ = "otp_codes"
    __table_args__ = (
        Index("ix_otp_codes_phone_purpose_created", "phone_number", "purpose", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    phone_number: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    purpose: Mapped[OtpPurpose] = mapped_column(Enum(OtpPurpose), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Carries registration input (preferred language) from the request-otp
    # step through to verify-otp, so no separate "pending registration"
    # table is needed.
    preferred_language: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class CashoutStatus(str, enum.Enum):
    DRAFT = "draft"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CONFIRMED = "confirmed"
    AWAITING_AUTHORIZATION = "awaiting_authorization"
    AUTHORIZED = "authorized"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SIMULATED = "simulated"


class CashoutRequest(Base):
    __tablename__ = "cashout_requests"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="GHS")
    status: Mapped[CashoutStatus] = mapped_column(
        Enum(CashoutStatus), default=CashoutStatus.AWAITING_CONFIRMATION
    )
    input_method: Mapped[str] = mapped_column(String(20), default="structured")
    language: Mapped[str] = mapped_column(String(10), default="tw")
    intent_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    user_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    authorization_status: Mapped[str] = mapped_column(String(30), default="not_started")
    transaction_reference: Mapped[str | None] = mapped_column(String(100))
    agent_message: Mapped[str | None] = mapped_column(Text)
    simulation: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    user = relationship("User", back_populates="cashouts")
    communications = relationship("Communication", back_populates="cashout")

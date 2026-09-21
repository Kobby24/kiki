import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class Communication(Base):
    __tablename__ = "communications"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    cashout_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cashout_requests.id"), index=True
    )
    language: Mapped[str] = mapped_column(String(10))
    message_type: Mapped[str] = mapped_column(String(40))
    text: Mapped[str] = mapped_column(Text)
    audio_reference: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    cashout = relationship("CashoutRequest", back_populates="communications")

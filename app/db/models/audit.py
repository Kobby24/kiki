import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    cashout_request_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cashout_requests.id")
    )
    action: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30))
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

import uuid
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.db.models.cashout import CashoutStatus


class CashoutCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: Decimal = Field(gt=0, le=100000, max_digits=12, decimal_places=2)
    currency: str = Field(default="GHS", pattern="^[A-Z]{3}$")
    language: str = Field(default="tw", min_length=2, max_length=10)
    input_method: str = Field(
        default="structured", pattern="^(speech|text|phrase|icon|structured)$"
    )


class ConfirmationRequest(BaseModel):
    confirmed: bool


class AuthorizationStatusRequest(BaseModel):
    status: str = Field(pattern="^(authorized|cancelled|failed)$")


class CashoutResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    amount: Decimal
    currency: str
    status: CashoutStatus
    language: str
    simulation: bool
    transaction_reference: str | None = None
    created_at: datetime


class CashoutCreated(CashoutResponse):
    message: str
    requires_confirmation: bool


class AuthorizationInstructions(BaseModel):
    cashout_id: uuid.UUID
    status: CashoutStatus
    authorization_method: str
    instructions: list[str]
    simulation: bool


class StatusResponse(BaseModel):
    cashout_id: uuid.UUID
    status: CashoutStatus
    simulation: bool


class ReceiptResponse(BaseModel):
    reference: str
    amount: Decimal
    currency: str
    status: CashoutStatus
    date: datetime
    simulation: bool

from decimal import Decimal
from pydantic import BaseModel, Field


class IntentRequest(BaseModel):
    input_type: str = Field(pattern="^(speech|text|phrase|icon|structured)$")
    text: str | None = Field(default=None, max_length=500)
    amount: Decimal | None = Field(default=None, gt=0, le=100000)
    language: str = Field(default="tw", min_length=2, max_length=10)


class IntentResponse(BaseModel):
    intent: str | None
    amount: Decimal | None
    currency: str
    language: str
    confidence: float
    requires_confirmation: bool
    requires_clarification: bool = False

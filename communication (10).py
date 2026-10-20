import uuid
from decimal import Decimal
from pydantic import BaseModel


class CommunicationResponse(BaseModel):
    cashout_id: uuid.UUID
    language: str
    text: str
    message_type: str
    cashout_amount: Decimal
    audio_reference: str | None = None

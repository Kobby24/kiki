import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.core.config import Settings
from app.db.models.cashout import CashoutRequest, CashoutStatus
from app.db.models.communication import Communication
from app.services.communication_service import CommunicationService
from app.services.momo.base import MomoProvider

TRANSITIONS = {
    CashoutStatus.AWAITING_CONFIRMATION: {
        CashoutStatus.CONFIRMED,
        CashoutStatus.CANCELLED,
    },
    CashoutStatus.CONFIRMED: {CashoutStatus.AWAITING_AUTHORIZATION},
    CashoutStatus.AWAITING_AUTHORIZATION: {
        CashoutStatus.AUTHORIZED,
        CashoutStatus.CANCELLED,
    },
    CashoutStatus.AUTHORIZED: {CashoutStatus.PROCESSING},
    CashoutStatus.PROCESSING: {CashoutStatus.COMPLETED, CashoutStatus.FAILED},
}


class CashoutService:
    def __init__(self, db: AsyncSession, provider: MomoProvider, settings: Settings):
        self.db = db
        self.provider = provider
        self.settings = settings
        self.communication = CommunicationService()

    async def get_owned(
        self, cashout_id: uuid.UUID, user_id: uuid.UUID
    ) -> CashoutRequest:
        cashout = await self.db.scalar(
            select(CashoutRequest).where(
                CashoutRequest.id == cashout_id, CashoutRequest.user_id == user_id
            )
        )
        if not cashout:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "CASHOUT_NOT_FOUND",
                    "message": "Cash-out request not found.",
                },
            )
        if cashout.created_at is None:
            cashout.created_at = cashout.updated_at or datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(cashout)
        return cashout

    async def transition(self, cashout: CashoutRequest, target: CashoutStatus) -> None:
        if target not in TRANSITIONS.get(cashout.status, set()):
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "INVALID_STATE_TRANSITION",
                    "message": f"Cannot move from {cashout.status.value} to {target.value}.",
                },
            )
        cashout.status = target
        await self.db.flush()

    async def confirm(self, cashout: CashoutRequest, confirmed: bool) -> CashoutRequest:
        await self.transition(
            cashout, CashoutStatus.CONFIRMED if confirmed else CashoutStatus.CANCELLED
        )
        cashout.user_confirmed = confirmed
        if confirmed:
            await self.transition(cashout, CashoutStatus.AWAITING_AUTHORIZATION)
        await self.db.commit()
        await self.db.refresh(cashout)
        return cashout

    async def start_authorization(self, cashout: CashoutRequest) -> CashoutRequest:
        if cashout.status != CashoutStatus.AWAITING_AUTHORIZATION:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "INVALID_STATE_TRANSITION",
                    "message": "Cash-out is not ready for authorization.",
                },
            )
        cashout.authorization_status = "started"
        await self.db.commit()
        await self.db.refresh(cashout)
        return cashout

    async def set_authorization_status(
        self, cashout: CashoutRequest, authorization_status: str
    ) -> CashoutRequest:
        if authorization_status == "authorized":
            await self.transition(cashout, CashoutStatus.AUTHORIZED)
            await self.transition(cashout, CashoutStatus.PROCESSING)
            cashout.transaction_reference = await self.provider.initiate_cashout(
                cashout.id, cashout.amount, cashout.currency
            )
            await self.transition(cashout, CashoutStatus.COMPLETED)
            cashout.authorization_status = "authorized"
            if self.provider.simulation:
                cashout.status = CashoutStatus.SIMULATED
        elif authorization_status == "cancelled":
            await self.transition(cashout, CashoutStatus.CANCELLED)
            cashout.authorization_status = "cancelled"
        else:
            await self.transition(cashout, CashoutStatus.FAILED)
            cashout.authorization_status = "failed"
        await self.db.commit()
        await self.db.refresh(cashout)
        return cashout

    async def create_communication(self, cashout: CashoutRequest) -> Communication:
        text = self.communication.agent_message(cashout.amount, cashout.language)
        communication = Communication(
            cashout_request_id=cashout.id,
            language=cashout.language,
            message_type="agent_message",
            text=text,
        )
        cashout.agent_message = text
        self.db.add(communication)
        await self.db.commit()
        await self.db.refresh(communication)
        return communication

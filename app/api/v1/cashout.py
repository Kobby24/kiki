import uuid
from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.core.dependencies import get_current_user
from app.db.models.cashout import CashoutRequest, CashoutStatus
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.cashout import (
    AuthorizationInstructions,
    AuthorizationStatusRequest,
    CashoutCreate,
    CashoutCreated,
    CashoutResponse,
    ConfirmationRequest,
    ReceiptResponse,
    StatusResponse,
)
from app.schemas.communication import CommunicationResponse
from app.services.cashout_service import CashoutService
from app.services.communication_service import CommunicationService
from app.services.momo.simulator import SimulationMomoProvider

router = APIRouter(prefix="/cashout", tags=["Cash-Out"])


def get_service(db: AsyncSession) -> CashoutService:
    settings = get_settings()
    return CashoutService(db, SimulationMomoProvider(), settings)


def response(cashout: CashoutRequest) -> CashoutResponse:
    return CashoutResponse.model_validate(cashout)


@router.post(
    "",
    response_model=CashoutCreated,
    status_code=201,
    summary="Create a cash-out request",
)
async def create_cashout(
    payload: CashoutCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    cashout = CashoutRequest(
        user_id=user.id,
        amount=payload.amount,
        currency=payload.currency,
        language=payload.language,
        input_method=payload.input_method,
        simulation=True,
    )
    db.add(cashout)
    await db.commit()
    await db.refresh(cashout)
    message = CommunicationService().confirmation_message(
        cashout.amount, cashout.language
    )
    return CashoutCreated(
        **response(cashout).model_dump(), message=message, requires_confirmation=True
    )


@router.get(
    "",
    response_model=list[CashoutResponse],
    summary="List the current user's cash-outs",
)
async def list_cashouts(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    cashouts = list(
        await db.scalars(
            select(CashoutRequest)
            .where(CashoutRequest.user_id == user.id)
            .order_by(CashoutRequest.created_at.desc())
        )
    )
    legacy_cashouts = [cashout for cashout in cashouts if cashout.created_at is None]
    if legacy_cashouts:
        fallback = datetime.now(timezone.utc)
        for cashout in legacy_cashouts:
            cashout.created_at = cashout.updated_at or fallback
        await db.commit()
    return cashouts


@router.get("/{cashout_id}", response_model=CashoutResponse, summary="Get a cash-out")
async def get_cashout(
    cashout_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await get_service(db).get_owned(cashout_id, user.id)


@router.post(
    "/{cashout_id}/confirm",
    response_model=CashoutResponse,
    summary="Confirm or cancel a cash-out",
)
async def confirm(
    cashout_id: uuid.UUID,
    payload: ConfirmationRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = get_service(db)
    return await service.confirm(
        await service.get_owned(cashout_id, user.id), payload.confirmed
    )


@router.post(
    "/{cashout_id}/authorization/start",
    response_model=AuthorizationInstructions,
    summary="Start user-controlled authorization",
)
async def start_authorization(
    cashout_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = get_service(db)
    cashout = await service.start_authorization(
        await service.get_owned(cashout_id, user.id)
    )
    return AuthorizationInstructions(
        cashout_id=cashout.id,
        status=cashout.status,
        authorization_method="user_momo_ussd",
        instructions=service.communication.authorization_instructions(cashout.language),
        simulation=True,
    )


@router.post(
    "/{cashout_id}/authorization/status",
    response_model=CashoutResponse,
    summary="Record simulation authorization status",
)
async def authorization_status(
    cashout_id: uuid.UUID,
    payload: AuthorizationStatusRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = get_service(db)
    return await service.set_authorization_status(
        await service.get_owned(cashout_id, user.id), payload.status
    )


@router.post(
    "/{cashout_id}/communication",
    response_model=CommunicationResponse,
    summary="Generate the agent message",
)
async def communication(
    cashout_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    cashout = await get_service(db).get_owned(cashout_id, user.id)
    item = await get_service(db).create_communication(cashout)
    return CommunicationResponse(
        cashout_id=cashout.id,
        language=item.language,
        text=item.text,
        message_type=item.message_type,
        cashout_amount=cashout.amount,
    )


@router.get(
    "/{cashout_id}/status",
    response_model=StatusResponse,
    summary="Get transaction status",
)
async def transaction_status(
    cashout_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    cashout = await get_service(db).get_owned(cashout_id, user.id)
    return StatusResponse(
        cashout_id=cashout.id, status=cashout.status, simulation=cashout.simulation
    )


@router.get(
    "/{cashout_id}/receipt",
    response_model=ReceiptResponse,
    summary="Get an accessible receipt",
)
async def receipt(
    cashout_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    cashout = await get_service(db).get_owned(cashout_id, user.id)
    if cashout.status not in {CashoutStatus.COMPLETED, CashoutStatus.SIMULATED}:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "RECEIPT_UNAVAILABLE",
                "message": "A receipt is available after completion.",
            },
        )
    return ReceiptResponse(
        reference=cashout.transaction_reference or str(cashout.id),
        amount=cashout.amount,
        currency=cashout.currency,
        status=cashout.status,
        date=cashout.updated_at or cashout.created_at,
        simulation=cashout.simulation,
    )

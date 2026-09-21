from fastapi import APIRouter
from app.schemas.intent import IntentRequest, IntentResponse
from app.services.intent_service import IntentService

router = APIRouter(prefix="/intent", tags=["Intent"])
service = IntentService()


@router.post(
    "/interpret",
    response_model=IntentResponse,
    summary="Interpret a proposed cash-out intent",
)
async def interpret(payload: IntentRequest):
    return service.interpret(payload)

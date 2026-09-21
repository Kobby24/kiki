from fastapi import APIRouter
from app.core.config import get_settings

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Check API health")
async def health():
    settings = get_settings()
    return {
        "status": "ok",
        "service": "sikapa-api",
        "environment": settings.environment,
    }

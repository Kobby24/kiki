from fastapi import APIRouter
from app.api.v1 import auth, cashout, health, intent

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(intent.router)
api_router.include_router(cashout.router)

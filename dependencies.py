import uuid
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import decode_subject
from app.db.models.user import User
from app.db.session import get_db

# Access tokens are only ever issued after OTP verification (see
# app/api/v1/auth.py) — there is no password grant, so a plain bearer
# scheme is used instead of OAuth2PasswordBearer.
bearer_scheme = HTTPBearer(auto_error=False, description="Access token from /auth/*/verify-otp")

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail={
        "error": "UNAUTHENTICATED",
        "message": "Invalid authentication credentials.",
    },
)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if credentials is None or not credentials.credentials:
        raise _UNAUTHENTICATED
    try:
        user_id = uuid.UUID(decode_subject(credentials.credentials))
    except (ValueError, AttributeError):
        raise _UNAUTHENTICATED
    user = await db.scalar(
        select(User).where(User.id == user_id, User.is_active.is_(True))
    )
    if not user:
        raise _UNAUTHENTICATED
    return user

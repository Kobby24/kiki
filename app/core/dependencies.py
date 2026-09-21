import uuid
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import decode_subject
from app.db.models.user import User
from app.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    try:
        user_id = uuid.UUID(decode_subject(token))
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "UNAUTHENTICATED",
                "message": "Invalid authentication credentials.",
            },
        )
    user = await db.scalar(
        select(User).where(User.id == user_id, User.is_active.is_(True))
    )
    if not user:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "UNAUTHENTICATED",
                "message": "Invalid authentication credentials.",
            },
        )
    return user

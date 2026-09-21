from typing import Annotated
from fastapi import APIRouter, Depends, Form, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register", response_model=UserResponse, status_code=201, summary="Register a user"
)
async def register(
    payload: RegisterRequest, db: Annotated[AsyncSession, Depends(get_db)]
):
    existing = await db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "EMAIL_EXISTS",
                "message": "An account with this email already exists.",
            },
        )
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        phone_number=payload.phone_number,
        preferred_language=payload.preferred_language,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse, summary="Log in")
async def login(payload: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "INVALID_CREDENTIALS",
                "message": "Email or password is incorrect.",
            },
        )
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/token", response_model=TokenResponse, include_in_schema=False)
async def token(
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await login(LoginRequest(email=username, password=password), db)


# @router.get("/me", response_model=UserResponse, summary="Get the current user")
# async def me(user: Annotated[User, Depends(get_current_user)]):
#     return user

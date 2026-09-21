from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import Settings, get_settings
from app.core.dependencies import get_current_user
from app.core.security import create_access_token
from app.db.models.otp import OtpPurpose
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequestOtp,
    LoginVerifyOtp,
    OtpRequestResponse,
    RegisterRequestOtp,
    RegisterVerifyOtp,
    TokenResponse,
    UserResponse,
)
from app.services.otp_service import OtpError, OtpService
from app.services.provider_factory import get_sms_provider

router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_otp_service(db: AsyncSession, settings: Settings) -> OtpService:
    try:
        sms_provider = get_sms_provider(settings)
    except RuntimeError as exc:
        # Misconfiguration (e.g. SMS_MODE=vonage without credentials set) —
        # fail as a clean 503 rather than an unhandled 500 traceback.
        raise HTTPException(
            status_code=503,
            detail={
                "error": "SMS_PROVIDER_UNAVAILABLE",
                "message": "The SMS provider is not available right now. Please try again later.",
            },
        ) from exc
    return OtpService(db, sms_provider, settings)


def _raise_otp_error(exc: OtpError) -> None:
    raise HTTPException(
        status_code=exc.status_code, detail={"error": exc.error, "message": exc.message}
    ) from exc


def _otp_response(phone_number: str, settings: Settings, debug_code: str | None = None):
    return OtpRequestResponse(
        message="A verification code has been sent to your phone number.",
        phone_number=phone_number,
        expires_in_seconds=settings.otp_ttl_seconds,
        resend_after_seconds=settings.otp_resend_cooldown_seconds,
        debug_code=debug_code,
    )


@router.post(
    "/register/request-otp",
    response_model=OtpRequestResponse,
    summary="Start registration: send an OTP to a new phone number",
)
async def register_request_otp(
    payload: RegisterRequestOtp, db: Annotated[AsyncSession, Depends(get_db)]
):
    existing = await db.scalar(select(User).where(User.phone_number == payload.phone_number))
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "PHONE_NUMBER_EXISTS",
                "message": "An account with this phone number already exists.",
            },
        )
    settings = get_settings()
    service = get_otp_service(db, settings)
    try:
        otp, debug_code = await service.request_otp(
            payload.phone_number,
            OtpPurpose.REGISTRATION,
            preferred_language=payload.preferred_language,
        )
    except OtpError as exc:
        _raise_otp_error(exc)
    return _otp_response(otp.phone_number, settings, debug_code)


@router.post(
    "/register/verify-otp",
    response_model=TokenResponse,
    status_code=201,
    summary="Complete registration by verifying the OTP",
)
async def register_verify_otp(
    payload: RegisterVerifyOtp, db: Annotated[AsyncSession, Depends(get_db)]
):
    # Re-check for a duplicate here too (not just at request-otp time): the
    # number may have been registered by a concurrent request in between.
    existing = await db.scalar(select(User).where(User.phone_number == payload.phone_number))
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "PHONE_NUMBER_EXISTS",
                "message": "An account with this phone number already exists.",
            },
        )

    settings = get_settings()
    service = get_otp_service(db, settings)
    try:
        otp = await service.verify_otp(payload.phone_number, OtpPurpose.REGISTRATION, payload.code)
    except OtpError as exc:
        _raise_otp_error(exc)

    user = User(
        phone_number=payload.phone_number,
        preferred_language=otp.preferred_language or "tw",
        phone_verified_at=otp.consumed_at,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        # A concurrent registration for the same number won the race; the
        # unique constraint on users.phone_number is the final guard.
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "error": "PHONE_NUMBER_EXISTS",
                "message": "An account with this phone number already exists.",
            },
        )
    await db.refresh(user)
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post(
    "/login/request-otp",
    response_model=OtpRequestResponse,
    summary="Start login: send an OTP to a registered phone number",
)
async def login_request_otp(
    payload: LoginRequestOtp, db: Annotated[AsyncSession, Depends(get_db)]
):
    settings = get_settings()
    user = await db.scalar(select(User).where(User.phone_number == payload.phone_number))
    if user and user.is_active:
        service = get_otp_service(db, settings)
        try:
            otp, debug_code = await service.request_otp(payload.phone_number, OtpPurpose.LOGIN)
        except OtpError as exc:
            _raise_otp_error(exc)
        return _otp_response(otp.phone_number, settings, debug_code)
    # Respond identically whether or not an account exists for this number,
    # so this endpoint can't be used to enumerate registered phone numbers.
    # No SMS is sent and no OTP row is created in this branch.
    return _otp_response(payload.phone_number, settings, debug_code=None)


@router.post(
    "/login/verify-otp",
    response_model=TokenResponse,
    summary="Complete login by verifying the OTP",
)
async def login_verify_otp(payload: LoginVerifyOtp, db: Annotated[AsyncSession, Depends(get_db)]):
    settings = get_settings()
    service = get_otp_service(db, settings)
    try:
        await service.verify_otp(payload.phone_number, OtpPurpose.LOGIN, payload.code)
    except OtpError as exc:
        _raise_otp_error(exc)

    user = await db.scalar(
        select(User).where(User.phone_number == payload.phone_number, User.is_active.is_(True))
    )
    if not user:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "INVALID_CREDENTIALS",
                "message": "Phone number or verification code is incorrect.",
            },
        )
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserResponse, summary="Get the current user")
async def me(user: Annotated[User, Depends(get_current_user)]):
    return user

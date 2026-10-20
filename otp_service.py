from datetime import datetime, timedelta, timezone
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import Settings
from app.core.security import generate_otp_code, hash_otp_code, verify_otp_code
from app.db.models.otp import OtpCode, OtpPurpose
from app.services.sms.base import SmsProvider


class OtpError(Exception):
    """Raised for any OTP request/verify failure. Carries an API-safe
    error code, human-readable message, and the HTTP status the caller
    should respond with."""

    def __init__(self, error: str, message: str, status_code: int = 400):
        self.error = error
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _aware(dt: datetime | None) -> datetime | None:
    """Normalize a datetime read back from the DB to timezone-aware UTC.

    SQLite (used in dev/test) does not reliably round-trip timezone info
    even for DateTime(timezone=True) columns, so values read back can come
    out naive. Comparisons below always go through this helper.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class OtpService:
    def __init__(self, db: AsyncSession, sms_provider: SmsProvider, settings: Settings):
        self.db = db
        self.sms = sms_provider
        self.settings = settings

    async def request_otp(
        self,
        phone_number: str,
        purpose: OtpPurpose,
        preferred_language: str | None = None,
    ) -> tuple[OtpCode, str | None]:
        """Issue a new OTP for phone_number/purpose, enforcing resend
        cooldown and hourly request limits. Returns the created row and,
        only in non-production debug mode, the plaintext code."""
        now = datetime.now(timezone.utc)

        window_start = now - timedelta(hours=1)
        recent_count = await self.db.scalar(
            select(func.count())
            .select_from(OtpCode)
            .where(
                OtpCode.phone_number == phone_number,
                OtpCode.purpose == purpose,
                OtpCode.created_at >= window_start,
            )
        )
        if recent_count and recent_count >= self.settings.otp_max_requests_per_hour:
            raise OtpError(
                "OTP_RATE_LIMITED",
                "Too many verification codes requested. Please try again later.",
                status_code=429,
            )

        last = await self.db.scalar(
            select(OtpCode)
            .where(OtpCode.phone_number == phone_number, OtpCode.purpose == purpose)
            .order_by(OtpCode.created_at.desc())
            .limit(1)
        )
        cooldown = timedelta(seconds=self.settings.otp_resend_cooldown_seconds)
        last_created_at = _aware(last.created_at) if last else None
        if last_created_at and (now - last_created_at) < cooldown:
            retry_after = int((cooldown - (now - last_created_at)).total_seconds())
            raise OtpError(
                "OTP_RESEND_TOO_SOON",
                f"Please wait {max(retry_after, 1)}s before requesting another code.",
                status_code=429,
            )

        code = generate_otp_code(self.settings.otp_length)
        otp = OtpCode(
            phone_number=phone_number,
            purpose=purpose,
            code_hash=hash_otp_code(phone_number, purpose.value, code),
            attempts=0,
            max_attempts=self.settings.otp_max_attempts,
            expires_at=now + timedelta(seconds=self.settings.otp_ttl_seconds),
            preferred_language=preferred_language,
        )
        self.db.add(otp)
        await self.db.commit()
        await self.db.refresh(otp)

        try:
            await self.sms.send_otp(phone_number, code, purpose.value)
        except Exception as exc:
            # Delivery failed: invalidate the code immediately so it can
            # never be verified even though it exists in the DB. The row
            # (and this attempt) still counts against the resend cooldown
            # and hourly cap above, so a persistently failing number can't
            # be used to hammer the SMS provider.
            otp.consumed_at = now
            await self.db.commit()
            raise OtpError(
                "OTP_DELIVERY_FAILED",
                "We couldn't send the verification code. Please try again shortly.",
                status_code=502,
            ) from exc

        debug_code = None
        if self.settings.environment != "production" and self.settings.otp_debug_expose_code:
            debug_code = code
        return otp, debug_code

    async def verify_otp(self, phone_number: str, purpose: OtpPurpose, code: str) -> OtpCode:
        """Validate a submitted code against the most recent unconsumed OTP
        for this phone/purpose, enforcing expiry and attempt limits."""
        otp = await self.db.scalar(
            select(OtpCode)
            .where(
                OtpCode.phone_number == phone_number,
                OtpCode.purpose == purpose,
                OtpCode.consumed_at.is_(None),
            )
            .order_by(OtpCode.created_at.desc())
            .limit(1)
        )
        if not otp:
            raise OtpError(
                "OTP_NOT_FOUND",
                "No active code was found for this phone number. Please request a new one.",
                status_code=400,
            )

        now = datetime.now(timezone.utc)

        if otp.attempts >= otp.max_attempts:
            raise OtpError(
                "OTP_LOCKED",
                "Too many incorrect attempts. Please request a new code.",
                status_code=400,
            )

        expires_at = _aware(otp.expires_at)
        if expires_at is not None and now > expires_at:
            raise OtpError(
                "OTP_EXPIRED",
                "This code has expired. Please request a new one.",
                status_code=400,
            )

        if not verify_otp_code(phone_number, purpose.value, code, otp.code_hash):
            otp.attempts += 1
            await self.db.commit()
            remaining = max(otp.max_attempts - otp.attempts, 0)
            message = (
                f"Incorrect code. {remaining} attempt(s) remaining."
                if remaining
                else "Incorrect code. Please request a new one."
            )
            raise OtpError("OTP_INVALID", message, status_code=400)

        otp.consumed_at = now
        await self.db.commit()
        await self.db.refresh(otp)
        return otp

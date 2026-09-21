import re
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator

# E.164: a leading '+', then 8-15 digits, first digit non-zero.
_PHONE_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")
_OTP_CODE_PATTERN = re.compile(r"^\d{4,8}$")


def _validate_phone_number(value: str) -> str:
    value = value.strip()
    if not _PHONE_PATTERN.match(value):
        raise ValueError(
            "Phone number must be in E.164 format, e.g. +233241234567."
        )
    return value


class PhoneNumberRequest(BaseModel):
    phone_number: str

    @field_validator("phone_number")
    @classmethod
    def _check_phone_number(cls, value: str) -> str:
        return _validate_phone_number(value)


class OtpCodeRequest(PhoneNumberRequest):
    code: str = Field(min_length=4, max_length=8)

    @field_validator("code")
    @classmethod
    def _check_code(cls, value: str) -> str:
        if not _OTP_CODE_PATTERN.match(value):
            raise ValueError("Verification code must be numeric.")
        return value


class RegisterRequestOtp(PhoneNumberRequest):
    preferred_language: str = Field(default="tw", max_length=10)


class RegisterVerifyOtp(OtpCodeRequest):
    pass


class LoginRequestOtp(PhoneNumberRequest):
    pass


class LoginVerifyOtp(OtpCodeRequest):
    pass


class OtpRequestResponse(BaseModel):
    message: str
    phone_number: str
    expires_in_seconds: int
    resend_after_seconds: int
    # Only populated outside production, when OTP_DEBUG_EXPOSE_CODE=true and
    # no real SMS provider is configured. Never populated in production.
    debug_code: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    phone_number: str
    preferred_language: str
    is_active: bool
    phone_verified_at: datetime | None

import hashlib
import hmac
import secrets
import string
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from app.core.config import get_settings

_OTP_ALPHABET = string.digits


def generate_otp_code(length: int | None = None) -> str:
    """Generate a cryptographically random numeric OTP code."""
    settings = get_settings()
    length = length or settings.otp_length
    return "".join(secrets.choice(_OTP_ALPHABET) for _ in range(length))


def hash_otp_code(phone_number: str, purpose: str, code: str) -> str:
    """HMAC an OTP code so plaintext codes are never persisted.

    The phone number and purpose are folded into the message so a hash
    cannot be replayed for a different phone number or a different flow
    (e.g. a login code can't be reused to satisfy a registration check).
    """
    settings = get_settings()
    message = f"{purpose}:{phone_number}:{code}".encode()
    return hmac.new(settings.jwt_secret_key.encode(), message, hashlib.sha256).hexdigest()


def verify_otp_code(phone_number: str, purpose: str, code: str, code_hash: str) -> bool:
    candidate = hash_otp_code(phone_number, purpose, code)
    return hmac.compare_digest(candidate, code_hash)


def create_access_token(subject: str) -> str:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return jwt.encode(
        {"sub": subject, "exp": expires},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_subject(token: str) -> str:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        subject = payload.get("sub")
        if not subject:
            raise ValueError("Missing token subject")
        return subject
    except (JWTError, ValueError) as exc:
        raise ValueError("Invalid token") from exc

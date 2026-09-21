from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from pwdlib import PasswordHash
from app.core.config import get_settings

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


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

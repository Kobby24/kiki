from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Sikapa API"
    environment: str = "development"
    debug: bool = False
    database_url: str = "sqlite+aiosqlite:///./sikapa.db"
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    momo_mode: str = "simulation"
    # "simulation" (no real SMS sent, logs only) or "vonage" (send via the
    # Vonage SMS API — requires vonage_api_key/vonage_api_secret below).
    sms_mode: str = "simulation"
    vonage_api_key: str = ""
    vonage_api_secret: str = ""
    # Sender ID shown to the recipient: an approved alphanumeric brand name
    # (where supported) or a Vonage virtual number in E.164 without '+'.
    vonage_sms_from: str = "Sikapa"
    vonage_sms_base_url: str = "https://rest.nexmo.com"
    vonage_sms_timeout_seconds: float = 10.0
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    intent_confidence_threshold: float = 0.75

    # OTP authentication tuning. Defaults are conservative production values;
    # override via environment variables (e.g. OTP_TTL_SECONDS) if needed.
    otp_length: int = 6
    otp_ttl_seconds: int = 300
    otp_max_attempts: int = 5
    otp_resend_cooldown_seconds: int = 60
    otp_max_requests_per_hour: int = 5
    # When true (and environment != "production"), OTP request responses
    # include the generated code so it can be used without a real SMS
    # provider configured. Must be disabled in production.
    otp_debug_expose_code: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()

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
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    intent_confidence_threshold: float = 0.75

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

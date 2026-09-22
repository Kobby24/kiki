"""
Configuration for the Sikapa AI/ML Communication Engine.

Reads HCI LAB API credentials and settings from environment variables.
Isolated from the ``app/core/config.py`` settings to maintain module separation.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AISettings(BaseSettings):
    """Settings for the AI subsystem — sourced from ``.env``."""

    hci_lab_api_base_url: str = "https://lab-subscription-platform.vercel.app/api/v1"
    hci_lab_api_key: str = ""
    hci_lab_tts_model_type: str = "ss"
    hci_lab_tts_speaker: str = "PT"
    hci_lab_timeout_seconds: float = 400.0  # 6.66 minutes: allows neural TTS/ASR model inference, cold-starts, & queueing

    # Cloudinary CDN for audio asset hosting
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_ai_settings() -> AISettings:
    """Return the cached AI settings singleton."""
    return AISettings()

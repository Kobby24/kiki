from app.core.config import Settings
from app.services.momo.base import MomoProvider
from app.services.momo.simulator import SimulationMomoProvider
from app.services.sms.base import SmsProvider
from app.services.sms.simulator import SimulationSmsProvider
from app.services.sms.vonage_provider import VonageSmsProvider


def get_momo_provider(settings: Settings) -> MomoProvider:
    if settings.momo_mode != "simulation":
        raise RuntimeError(
            "No official Mobile Money provider is configured; use MOMO_MODE=simulation."
        )
    return SimulationMomoProvider()


def get_sms_provider(settings: Settings) -> SmsProvider:
    if settings.sms_mode == "simulation":
        return SimulationSmsProvider()
    if settings.sms_mode == "vonage":
        return VonageSmsProvider(
            api_key=settings.vonage_api_key,
            api_secret=settings.vonage_api_secret,
            from_id=settings.vonage_sms_from,
            base_url=settings.vonage_sms_base_url,
            timeout=settings.vonage_sms_timeout_seconds,
        )
    raise RuntimeError(
        f"Unsupported SMS_MODE '{settings.sms_mode}'; use 'simulation' or 'vonage'."
    )

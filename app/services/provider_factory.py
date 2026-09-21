from app.core.config import Settings
from app.services.momo.base import MomoProvider
from app.services.momo.simulator import SimulationMomoProvider


def get_momo_provider(settings: Settings) -> MomoProvider:
    if settings.momo_mode != "simulation":
        raise RuntimeError(
            "No official Mobile Money provider is configured; use MOMO_MODE=simulation."
        )
    return SimulationMomoProvider()

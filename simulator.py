from decimal import Decimal
from uuid import UUID
from app.services.momo.base import MomoProvider


class SimulationMomoProvider(MomoProvider):
    simulation = True

    async def initiate_cashout(
        self, cashout_id: UUID, amount: Decimal, currency: str
    ) -> str:
        return f"SIM-{str(cashout_id).replace('-', '').upper()[:12]}"

    async def get_transaction_status(self, reference: str) -> str:
        return "completed" if reference.startswith("SIM-") else "failed"

    async def cancel_authorization(self, reference: str) -> None:
        return None

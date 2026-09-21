from abc import ABC, abstractmethod
from decimal import Decimal
from uuid import UUID


class MomoProvider(ABC):
    simulation: bool = False

    @abstractmethod
    async def initiate_cashout(
        self, cashout_id: UUID, amount: Decimal, currency: str
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def get_transaction_status(self, reference: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def cancel_authorization(self, reference: str) -> None:
        raise NotImplementedError

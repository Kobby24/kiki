from abc import ABC, abstractmethod


class SmsProvider(ABC):
    """Sends OTP codes by SMS. See app/services/momo/base.py for the same
    provider-abstraction pattern applied to Mobile Money."""

    simulation: bool = False

    @abstractmethod
    async def send_otp(self, phone_number: str, code: str, purpose: str) -> str:
        """Send an OTP SMS and return an opaque provider delivery reference."""
        raise NotImplementedError

import logging
from app.services.sms.base import SmsProvider

logger = logging.getLogger("sikapa.sms.simulator")


class SimulationSmsProvider(SmsProvider):
    """Does not send a real SMS. Logs the delivery so the code is visible
    in application logs during development, and returns a fake reference.

    The actual code reaches the caller (and, in non-production
    environments, the API response) via OtpService; this provider never
    needs to inspect or return the code itself beyond logging it.
    """

    simulation = True

    async def send_otp(self, phone_number: str, code: str, purpose: str) -> str:
        logger.info(
            "Simulated OTP SMS to %s for %s: %s", phone_number, purpose, code
        )
        masked = phone_number[-4:] if len(phone_number) >= 4 else phone_number
        return f"SIM-SMS-{masked}"

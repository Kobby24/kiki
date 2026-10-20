import logging
import re
import httpx
from app.services.sms.base import SmsProvider

logger = logging.getLogger("sikapa.sms.vonage")

# Vonage's SMS API (https://rest.nexmo.com/sms/json) wants MSISDNs without
# a leading '+' or international dial-out prefix — just the country code
# followed by the number, e.g. "233241234567" for "+233241234567".
# See: https://developer.vonage.com/en/messaging/sms/technical-details
_LEADING_PLUS_OR_ZEROS = re.compile(r"^(\+|00)")

# The GSM 03.38 "basic character set". Anything outside it (accented Twi
# vowels like ɛ/ɔ, emoji, etc.) must be sent with type=unicode or Vonage
# will drop/mangle the characters — the legacy SMS API does not
# auto-detect this the way the newer Messages API does.
_GSM_7_BASIC = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ ÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)


def _to_vonage_msisdn(phone_number: str) -> str:
    return _LEADING_PLUS_OR_ZEROS.sub("", phone_number)


def _needs_unicode_encoding(text: str) -> bool:
    return any(char not in _GSM_7_BASIC for char in text)


class VonageSmsError(RuntimeError):
    """Raised when the Vonage SMS API accepts the HTTP request but reports
    a non-zero per-message status (see the SMS API error code table)."""

    def __init__(self, status: str, error_text: str | None):
        self.status = status
        self.error_text = error_text
        super().__init__(f"Vonage SMS API returned status {status}: {error_text}")


class VonageSmsProvider(SmsProvider):
    """Sends OTP codes via the Vonage SMS API.

    Talks directly to https://rest.nexmo.com/sms/json over HTTP with an
    async client (rather than the official, synchronous vonage-python SDK)
    so it doesn't block the event loop in this async FastAPI app.
    Authenticates with API key/secret HTTP Basic auth, per Vonage's
    documented approach:
    https://developer.vonage.com/en/messaging/sms/technical-details
    """

    simulation = False

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        from_id: str,
        base_url: str = "https://rest.nexmo.com",
        timeout: float = 10.0,
    ):
        if not api_key or not api_secret:
            raise RuntimeError(
                "Vonage SMS is not configured: set VONAGE_API_KEY and "
                "VONAGE_API_SECRET (or switch SMS_MODE back to 'simulation')."
            )
        self._api_key = api_key
        self._api_secret = api_secret
        self._from_id = from_id
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def _build_message(self, code: str, purpose: str) -> str:
        return f"Your Sikapa verification code is {code}. It expires shortly. Do not share this code with anyone."

    async def send_otp(self, phone_number: str, code: str, purpose: str) -> str:
        text = self._build_message(code, purpose)
        payload = {
            "api_key": self._api_key,
            "api_secret": self._api_secret,
            "from": self._from_id,
            "to": _to_vonage_msisdn(phone_number),
            "text": text,
        }
        if _needs_unicode_encoding(text):
            payload["type"] = "unicode"

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.post(f"{self._base_url}/sms/json", data=payload)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.error("Vonage SMS request failed for %s: %s", phone_number, exc)
                raise RuntimeError("Failed to reach the SMS provider.") from exc

        body = response.json()
        messages = body.get("messages") or []
        if not messages:
            logger.error("Vonage SMS API returned an unexpected response: %s", body)
            raise RuntimeError("Vonage SMS API returned an unexpected response.")

        result = messages[0]
        status = result.get("status")
        if status != "0":
            error_text = result.get("error-text")
            logger.error(
                "Vonage SMS to %s failed with status %s: %s",
                phone_number,
                status,
                error_text,
            )
            raise VonageSmsError(status, error_text)

        return result.get("message-id", "")

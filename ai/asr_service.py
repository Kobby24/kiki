"""
Automatic Speech Recognition (ASR) service layer.

Calls the HCI LAB ASR API (``POST /api/v1/asr``) with file-based
caching to conserve the strict daily/weekly quota.  Keeps the abstract
base class so a different backend can be swapped in later.
"""

from abc import ABC, abstractmethod
import logging

import httpx

from ai.cache import get_asr_cache, set_asr_cache
from ai.ai_config import get_ai_settings
from ai.schemas import ASRResult

logger = logging.getLogger(__name__)


# Abstract base – the contract every ASR backend must fulfil

class BaseASRService(ABC):
    """Interface that any ASR engine must implement."""

    @abstractmethod
    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
    ) -> ASRResult:
        """Transcribe audio bytes into text.

        Parameters
        ----------
        audio_bytes:
            Raw audio file content (any format accepted by the backend).
        filename:
            Original filename — helps the backend detect the audio format.

        Returns
        -------
        ASRResult
            Transcript and fallback flag.
        """
        ...


# HCI LAB implementation

class HCILabASRService(BaseASRService):
    """Calls the University of Ghana HCI LAB Speech-to-Text API.

    * Checks the file-based cache before making an API call.
    * Caches successful transcripts to avoid burning quota on duplicates.
    """

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
    ) -> ASRResult:
        # ------ empty input guard ------ #
        if not audio_bytes:
            return ASRResult(
                transcript="",
                requires_manual_fallback=True,
            )

        # ------ cache lookup ------ #
        cached_transcript = get_asr_cache(audio_bytes)
        if cached_transcript is not None:
            logger.info("ASR cache hit")
            return ASRResult(transcript=cached_transcript)

        # ------ call HCI LAB API ------ #
        settings = get_ai_settings()
        if not settings.hci_lab_api_key:
            raise RuntimeError(
                "HCI_LAB_API_KEY is not configured. "
                "Set it in your .env file to enable ASR."
            )

        logger.info("Calling HCI LAB ASR API (quota consumed)")
        timeout = httpx.Timeout(timeout=settings.hci_lab_timeout_seconds, connect=30.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{settings.hci_lab_api_base_url}/asr",
                    headers={"Authorization": f"Bearer {settings.hci_lab_api_key}"},
                    files={"file": (filename, audio_bytes)},
                )
        except httpx.TimeoutException as exc:
            raise RuntimeError(
                f"HCI LAB ASR timed out after {settings.hci_lab_timeout_seconds:.0f}s. "
                f"The remote ASR model took too long to transcribe audio."
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(f"HCI LAB ASR network connection error: {exc}") from exc

        # ------ handle errors ------ #
        if response.status_code != 200:
            error_detail = _parse_api_error(response)
            raise RuntimeError(
                f"HCI LAB ASR error ({response.status_code}): {error_detail}"
            )

        # ------ parse transcript ------ #
        transcript = _extract_transcript(response)
        set_asr_cache(audio_bytes, transcript)

        return ASRResult(transcript=transcript)


# Response helpers

def _extract_transcript(response: httpx.Response) -> str:
    """Best-effort extraction of the transcript from the API response."""
    content_type = response.headers.get("content-type", "")

    if "json" in content_type or "text" not in content_type:
        try:
            data = response.json()
            if isinstance(data, str):
                return data
            if isinstance(data, dict):
                # Try common field names
                for key in ("transcript", "text", "transcription", "result"):
                    if key in data and isinstance(data[key], str):
                        return data[key]
                return str(data)
        except (ValueError, KeyError):
            pass

    # Fall back to raw text
    return response.text.strip()


def _parse_api_error(response: httpx.Response) -> str:
    """Extract a human-readable error message from an API error response per HCI LAB schema."""
    try:
        data = response.json()
        if isinstance(data, dict):
            req_id = data.get("request_id")
            error = data.get("error", {})
            if isinstance(error, dict):
                code = error.get("code")
                msg = error.get("message", str(error))
                prefix = f"[{code}] " if code else ""
                suffix = f" (request_id: {req_id})" if req_id else ""
                return f"{prefix}{msg}{suffix}"
            suffix = f" (request_id: {req_id})" if req_id else ""
            return f"{error}{suffix}"
        return str(data)
    except (ValueError, KeyError):
        return response.text[:500]


# Factory – single place to swap implementations

_current_service: BaseASRService | None = None


def get_asr_service() -> BaseASRService:
    """Return the active ASR service instance (lazy singleton)."""
    global _current_service
    if _current_service is None:
        _current_service = HCILabASRService()
    return _current_service


def set_asr_service(service: BaseASRService) -> None:
    """Replace the active ASR service (e.g. for testing)."""
    global _current_service
    _current_service = service

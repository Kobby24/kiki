"""
Pydantic v2 schemas and enums for the Sikapa AI/ML Communication Engine.

Defines the core data contracts for ASR results, NLU slot extractions,
audio synthesis requests, and the enumerations they depend on.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class IntentType(str, Enum):
    """Transactional intents recognised by the NLU engine."""

    WITHDRAW = "WITHDRAW"
    TRANSFER = "TRANSFER"
    DEPOSIT = "DEPOSIT"
    UNKNOWN = "UNKNOWN"


class AudioMode(str, Enum):
    """Playback modes supported by the audio synthesis engine."""

    FULL = "FULL"
    REPEAT_AMOUNT = "REPEAT_AMOUNT"
    REPEAT_NUMBER_NORMAL = "REPEAT_NUMBER_NORMAL"
    REPEAT_NUMBER_BOKOO = "REPEAT_NUMBER_BOKOO"
    POLITENESS = "POLITENESS"


# ASR

class ASRResult(BaseModel):
    """Result returned by the Automatic Speech Recognition service."""

    transcript: str = Field(..., description="Transcribed text from the audio input.")
    requires_manual_fallback: bool = Field(
        default=False,
        description=(
            "When True the client should present the icon-grid fallback UI. "
            "Automatically set when transcription is empty or speech was not recognized."
        ),
    )

    @model_validator(mode="after")
    def _apply_fallback_flag(self) -> "ASRResult":
        """Guardrail: flag empty or unparsed transcripts for manual fallback."""
        if not self.transcript or not self.transcript.strip():
            self.requires_manual_fallback = True
        return self


# NLU

class NLUSlotExtraction(BaseModel):
    """Extracted intent and transactional slots from a Twi/English utterance."""

    intent: IntentType = Field(
        default=IntentType.UNKNOWN,
        description="Detected transactional intent.",
    )
    amount: Optional[float] = Field(
        default=None,
        description="Monetary amount extracted from the utterance.",
    )
    currency: str = Field(
        default="GHS",
        description="ISO currency code; defaults to Ghana Cedi.",
    )
    recipient: Optional[str] = Field(
        default=None,
        description="Recipient name, if mentioned (e.g. after 'ma').",
    )
    recipient_phone: Optional[str] = Field(
        default=None,
        description="10-digit Ghanaian phone number of the recipient.",
    )
    raw_text: str = Field(
        ...,
        description="Original text that was analysed.",
    )


# Audio Synthesis

class SynthesizeAudioRequest(BaseModel):
    """Request body for the /ai/synthesize endpoint."""

    intent: IntentType = Field(
        default=IntentType.UNKNOWN,
        description="Transaction intent for the audio response.",
    )
    amount: Optional[float] = Field(
        default=None,
        gt=0,
        description="Monetary amount to speak (required for FULL and REPEAT_AMOUNT).",
    )
    currency: str = Field(default="GHS", description="Currency code.")
    phone_number: Optional[str] = Field(
        default=None,
        description="Recipient phone number (10-digit, starts with '0').",
    )
    mode: AudioMode = Field(
        default=AudioMode.FULL,
        description="Audio playback mode.",
    )


class SynthesizeAudioResponse(BaseModel):
    """JSON response from the /ai/synthesize endpoint.

    Contains a Cloudinary CDN URL that the frontend can use directly
    in an ``<audio>`` element for instant, seekable playback.
    """

    audio_url: str = Field(
        ...,
        description="HTTPS Cloudinary CDN URL for the synthesized audio.",
    )
    mode: AudioMode = Field(
        ...,
        description="The audio mode that was used to generate this response.",
    )


# Pipeline (convenience combo response)

class PipelineResult(BaseModel):
    """Combined ASR + NLU result returned by the process-pipeline endpoint."""

    asr: ASRResult
    nlu: NLUSlotExtraction

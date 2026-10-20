"""
FastAPI router for the Sikapa AI/ML Communication Engine.

All endpoints are prefixed with ``/ai`` and grouped under the *AI* tag
in the OpenAPI / Swagger UI docs.  Audio endpoints accept the full range
of formats supported by the HCI LAB API.
"""

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from ai.asr_service import get_asr_service
from ai.audio_service import synthesize
from ai.nlu_service import extract_slots
from ai.schemas import (
    ASRResult,
    NLUSlotExtraction,
    PipelineResult,
    SynthesizeAudioRequest,
    SynthesizeAudioResponse,
)

ai_router = APIRouter(prefix="/ai", tags=["AI"])

# Audio formats accepted by the HCI LAB ASR API
_ACCEPTED_AUDIO_TYPES = {
    "audio/wav",
    "audio/wave",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/ogg",
    "audio/opus",
    "audio/flac",
    "audio/mp4",
    "audio/m4a",
    "audio/aac",
    "audio/webm",
    "audio/aiff",
    "audio/x-aiff",
    "audio/x-ms-wma",
    "audio/amr",
    "application/octet-stream",
}


# Request bodies

class ExtractIntentRequest(BaseModel):
    """JSON body for the /ai/extract-intent endpoint."""
    text: str = Field(..., min_length=1, description="Transcribed or typed utterance.")


# Helpers

def _validate_audio_upload(file: UploadFile) -> None:
    """Raise 415 if the uploaded file's content type is not audio."""
    if file.content_type and file.content_type not in _ACCEPTED_AUDIO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported audio format: {file.content_type}. "
                "Supported: wav, mp3, ogg, opus, flac, m4a, mp4, aac, webm, aiff, wma, amr."
            ),
        )


def _handle_service_error(exc: Exception) -> HTTPException:
    """Convert a service-layer error into an appropriate HTTP exception."""
    message = str(exc)
    if "not configured" in message:
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=message,
        )
    if "quota" in message.lower() or "limit" in message.lower():
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=message,
        )
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Upstream API error: {message}",
    )


# POST /ai/transcribe

@ai_router.post(
    "/transcribe",
    response_model=ASRResult,
    summary="Transcribe audio to text",
    description=(
        "Accepts an audio file via multipart/form-data and returns "
        "an ASR result with transcript and fallback flag. "
        "Supported formats: wav, mp3, ogg, opus, flac, m4a, aac, webm, aiff, wma, amr."
    ),
)
async def transcribe_audio(
    file: Annotated[UploadFile, File(description="Audio file to transcribe")],
) -> ASRResult:
    _validate_audio_upload(file)

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded audio file is empty.",
        )

    try:
        asr = get_asr_service()
        return await asr.transcribe(audio_bytes, filename=file.filename or "audio.wav")
    except RuntimeError as exc:
        raise _handle_service_error(exc)


# POST /ai/extract-intent

@ai_router.post(
    "/extract-intent",
    response_model=NLUSlotExtraction,
    summary="Extract intent and slots from text",
    description=(
        "Analyses a Twi/English utterance and returns the detected "
        "transactional intent along with extracted slots (amount, phone, name). "
        "This endpoint is purely local — no external API call is made."
    ),
)
async def extract_intent(body: ExtractIntentRequest) -> NLUSlotExtraction:
    return extract_slots(body.text)


# POST /ai/process-pipeline

@ai_router.post(
    "/process-pipeline",
    response_model=PipelineResult,
    summary="Full ASR → NLU pipeline",
    description=(
        "Single-call convenience endpoint: accepts an audio file, runs ASR "
        "transcription followed by NLU slot extraction, and returns both "
        "results together."
    ),
)
async def process_pipeline(
    file: Annotated[UploadFile, File(description="Audio file to transcribe")],
) -> PipelineResult:
    _validate_audio_upload(file)

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded audio file is empty.",
        )

    try:
        asr_service = get_asr_service()
        asr_result = await asr_service.transcribe(
            audio_bytes, filename=file.filename or "audio.wav",
        )
    except RuntimeError as exc:
        raise _handle_service_error(exc)

    nlu_result = extract_slots(asr_result.transcript)
    return PipelineResult(asr=asr_result, nlu=nlu_result)


# POST /ai/synthesize

@ai_router.post(
    "/synthesize",
    response_model=SynthesizeAudioResponse,
    summary="Synthesize code-mixed audio response",
    description=(
        "Generates or retrieves a spoken audio response and returns a "
        "Cloudinary CDN URL. The frontend can use this URL directly in "
        "an <audio> element for instant playback with full seeking support."
    ),
)
async def synthesize_audio(body: SynthesizeAudioRequest) -> SynthesizeAudioResponse:
    try:
        audio_url = await synthesize(body)
    except RuntimeError as exc:
        raise _handle_service_error(exc)

    return SynthesizeAudioResponse(audio_url=audio_url, mode=body.mode)


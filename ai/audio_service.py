"""
Audio response engine with code-mixed Twi/English synthesis.

Generates spoken audio via the HCI LAB TTS API or by stitching
pre-baked Edge TTS clips locally. All generated audio is uploaded
to Cloudinary CDN and the resulting URL is returned to the frontend.

Cache hierarchy:
    1. Cloudinary URL cache (in-memory) — instant URL return
    2. Local disk/memory cache — avoids redundant TTS API calls
    3. Cloudinary CDN — persistent, globally distributed storage
    4. HCI LAB TTS API — only called on absolute cache miss
"""

import io
import logging
import wave

import httpx

from ai.amount_builder import amount_to_words
from ai.cache import (
    get_asset_audio,
    get_tts_cache,
    set_asset_audio,
    set_tts_cache,
)
from ai.cloudinary_storage import (
    build_cdn_url,
    build_public_id,
    get_cached_url,
    upload_audio_bytes,
)
from ai.ai_config import get_ai_settings
from ai.schemas import AudioMode, IntentType, SynthesizeAudioRequest

logger = logging.getLogger(__name__)

# Politeness standard text
_POLITENESS_TEXT = "Mepaakyɛw, ma mentemu mma wo bio"

# English digit words (per Ghana user preference: spoken in English)
_DIGIT_WORDS: dict[str, str] = {
    "0": "zero",
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
}

# Pause durations for phone-number playback
_PAUSE_NORMAL_MS = 50   # Faster, natural conversational digit flow
_PAUSE_BOKOO_MS = 150   # Deliberate, clear cadence for accessibility / verification

# High-efficiency in-memory caches (RAM-resident for sub-millisecond execution)
# Stores pre-computed silence bytes: {(duration_ms, sample_rate, frame_size): silence_bytes}
_SILENCE_CACHE: dict[tuple[int, int, int], bytes] = {}


# --- HCI LAB TTS API caller (with multi-tier cache) --- #

async def _call_tts_api(text: str, bypass_cache: bool = False) -> bytes:
    """Call the HCI LAB TTS API and return WAV bytes.

    Resolves audio through multi-tier cache:
    1. L1 RAM Memory Cache
    2. L2 Named Pre-baked Assets
    3. L3 Disk Cache (SHA-256)
    4. L4 Remote API (only on absolute cache miss)
    """
    # L1 / L3 cache hit
    if not bypass_cache:
        cached = get_tts_cache(text)
        if cached is not None:
            logger.info("TTS cache hit for: %s", text[:60])
            return cached

    # Remote API call
    settings = get_ai_settings()
    if not settings.hci_lab_api_key:
        raise RuntimeError(
            "HCI_LAB_API_KEY is not configured. "
            "Set it in your .env file to enable TTS."
        )

    logger.info("Calling HCI LAB TTS API (quota consumed): %s", text[:60])
    timeout = httpx.Timeout(timeout=settings.hci_lab_timeout_seconds, connect=30.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{settings.hci_lab_api_base_url}/tts",
                headers={"Authorization": f"Bearer {settings.hci_lab_api_key}"},
                json={
                    "text": text,
                    "model_type": settings.hci_lab_tts_model_type,
                    "speaker": settings.hci_lab_tts_speaker,
                },
            )
    except httpx.TimeoutException as exc:
        raise RuntimeError(
            f"HCI LAB TTS timed out after {settings.hci_lab_timeout_seconds:.0f}s. "
            f"The remote TTS model took too long to synthesize audio."
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"HCI LAB TTS network connection error: {exc}") from exc

    if response.status_code != 200:
        error_msg = _parse_api_error(response)
        raise RuntimeError(
            f"HCI LAB TTS error ({response.status_code}): {error_msg}"
        )

    content_type = response.headers.get("content-type", "")
    if "audio" not in content_type:
        error_msg = _parse_api_error(response)
        raise RuntimeError(f"TTS returned non-audio response: {error_msg}")

    wav_bytes = response.content
    req_id = response.headers.get("x-request-id", "unknown")
    dur_sec = response.headers.get("x-duration-sec", "unknown")
    chars_used = response.headers.get("x-characters-used", "unknown")
    logger.info(
        "HCI LAB TTS success: req_id=%s, duration=%ss, chars=%s, bytes=%d",
        req_id,
        dur_sec,
        chars_used,
        len(wav_bytes),
    )

    set_tts_cache(text, wav_bytes)
    return wav_bytes


def _parse_api_error(response: httpx.Response) -> str:
    """Extract a human-readable message from an API error response per HCI LAB schema."""
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


# --- Text builders (First-Person Voice for AAC Dignity) --- #

def _format_amount(amount: float | None) -> str:
    """Format amount for spoken output."""
    if amount is None:
        return "0"
    if amount == int(amount):
        return str(int(amount))
    return f"{amount:.2f}"


def _build_full_text(request: SynthesizeAudioRequest) -> str:
    """Build first-person code-mixed message matching app communication."""
    amount_str = _format_amount(request.amount)
    if request.intent == IntentType.WITHDRAW:
        return f"Mepa wo kyɛw, mepɛ sɛ megye GHS {amount_str} fi me Mobile Money so."
    if request.intent == IntentType.TRANSFER:
        if request.phone_number:
            digits_spaced = " ".join(request.phone_number)
            return f"Mepa wo kyɛw, mepɛ sɛ mede GHS {amount_str} kɔma {digits_spaced} fi me Mobile Money so."
        return f"Mepa wo kyɛw, mepɛ sɛ mede GHS {amount_str} kɔma fi me Mobile Money so."
    if request.intent == IntentType.DEPOSIT:
        return f"Mepa wo kyɛw, mepɛ sɛ mede GHS {amount_str} gu me account mu."
    return f"Mepa wo kyɛw, mepɛ sɛ megye GHS {amount_str}."


def _build_amount_text(request: SynthesizeAudioRequest) -> str:
    """Build the amount-only text for REPEAT_AMOUNT mode."""
    return f"{_format_amount(request.amount)} Ghana cedis"


# --- WAV stitching helpers (Optimized In-Memory PCM Operations) --- #

def _read_wav_pcm(wav_bytes: bytes) -> tuple[bytes, int, int, int]:
    """Read a WAV container and return (pcm_data, sample_rate, sample_width, n_channels)."""
    buf = io.BytesIO(wav_bytes)
    with wave.open(buf, "rb") as wf:
        return (
            wf.readframes(wf.getnframes()),
            wf.getframerate(),
            wf.getsampwidth(),
            wf.getnchannels(),
        )


def _pack_wav(
    pcm: bytes,
    sample_rate: int,
    sample_width: int,
    n_channels: int,
) -> bytes:
    """Wrap raw PCM data in a WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(n_channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def _silence_pcm(duration_ms: int, sample_rate: int, frame_size: int) -> bytes:
    """Generate silent PCM frames with memoized caching."""
    cache_key = (duration_ms, sample_rate, frame_size)
    if cache_key in _SILENCE_CACHE:
        return _SILENCE_CACHE[cache_key]

    n_frames = int(sample_rate * duration_ms / 1000)
    silence = b"\x00" * (n_frames * frame_size)
    _SILENCE_CACHE[cache_key] = silence
    return silence


async def _get_asset_clip(key: str) -> bytes:
    """Retrieve raw audio clip for an asset key."""
    clip = get_asset_audio("en_digits", f"{key}.wav")
    if clip is None:
        # Fallback to API if a key is completely missing
        word = _DIGIT_WORDS.get(key, key)
        clip = await _call_tts_api(word)
    return clip


async def _stitch_audio_sequence(keys: list[str], pause_ms: int) -> bytes:
    """Build continuous audio from a sequence of keys with pauses between them.

    Supports both RIFF PCM WAV and stream audio (e.g. MP3) seamlessly.
    """
    if not keys:
        raise RuntimeError("No valid audio keys found in sequence.")

    clips = [await _get_asset_clip(k) for k in keys]
    first_clip = clips[0]

    # Mode 1: True RIFF WAV files (parse PCM frames and stitch)
    if first_clip.startswith(b"RIFF"):
        pcm_items = [_read_wav_pcm(c) for c in clips]
        _, sr, sw, nc = pcm_items[0]
        frame_size = sw * nc
        silence = _silence_pcm(pause_ms, sr, frame_size)

        pcm_parts: list[bytes] = []
        for i, (pcm, _, _, _) in enumerate(pcm_items):
            pcm_parts.append(pcm)
            if i < len(pcm_items) - 1:
                pcm_parts.append(silence)

        return _pack_wav(b"".join(pcm_parts), sr, sw, nc)

    # Mode 2: Stream audio (e.g. MP3 from edge-tts)
    parts: list[bytes] = []
    
    if pause_ms > 0:
        # Match Edge-TTS 48kbps MPEG-2 L3 Mono header: FF F3 64 C4
        # Frame size: 72 * 48000 / 22050 + 1 (padding) = 157 bytes. 
        # (157 - 4 header = 153 payload)
        silent_frame = b"\xff\xf3\x64\xc4" + b"\x00" * 153
        # Approx 26ms per frame at 22050Hz
        frame_count = max(1, round(pause_ms / 26))
        silence = silent_frame * frame_count

        for i, clip in enumerate(clips):
            parts.append(clip)
            if i < len(clips) - 1:
                parts.append(silence)
    else:
        # Gapless stitching (e.g. for amounts)
        parts = clips

    return b"".join(parts)


# --- Cloudinary upload helpers --- #

def _upload_stitched(audio_bytes: bytes, public_id: str) -> str:
    """Upload stitched audio to Cloudinary and return the CDN URL.

    Uses a deterministic ``public_id`` so the same combination of
    digits or amount words is only uploaded once. Subsequent requests
    for the same content return the cached URL instantly.
    """
    # Check in-memory URL cache first (zero I/O)
    cached = get_cached_url(public_id)
    if cached:
        return cached

    return upload_audio_bytes(audio_bytes, public_id, file_format="mp3")


def _upload_tts_result(audio_bytes: bytes, public_id: str) -> str:
    """Upload a TTS API result to Cloudinary and return the CDN URL.

    HCI LAB returns WAV audio, so we upload with wav format.
    """
    cached = get_cached_url(public_id)
    if cached:
        return cached

    # Detect format from the audio header
    fmt = "wav" if audio_bytes.startswith(b"RIFF") else "mp3"
    return upload_audio_bytes(audio_bytes, public_id, file_format=fmt)


# --- Public synthesis API --- #

async def synthesize(request: SynthesizeAudioRequest) -> str:
    """Generate or retrieve audio for the given synthesis request.

    Returns a Cloudinary CDN URL that the frontend can use directly
    in an ``<audio>`` element for instant, seekable playback.
    """
    if request.mode == AudioMode.FULL:
        # Build a deterministic public_id from the request parameters
        amount_key = _format_amount(request.amount).replace(".", "_")
        phone_key = request.phone_number or "none"
        pid = build_public_id(
            "full",
            f"{request.intent.value}_{amount_key}_{phone_key}",
        )
        cached = get_cached_url(pid)
        if cached:
            return cached

        text = _build_full_text(request)
        audio = await _call_tts_api(text)
        return _upload_tts_result(audio, pid)

    if request.mode == AudioMode.REPEAT_AMOUNT:
        # Deterministic key: e.g. "sikapa/amounts/125_50"
        amount_key = _format_amount(request.amount).replace(".", "_")
        pid = build_public_id("amounts", amount_key)
        cached = get_cached_url(pid)
        if cached:
            return cached

        keys = amount_to_words(request.amount)
        audio = await _stitch_audio_sequence(keys, 0)
        return _upload_stitched(audio, pid)

    if request.mode == AudioMode.REPEAT_NUMBER_NORMAL:
        if request.phone_number:
            digits = [ch for ch in request.phone_number if ch.isdigit()]
            pid = build_public_id("phone_normal", "".join(digits))
            cached = get_cached_url(pid)
            if cached:
                return cached

            audio = await _stitch_audio_sequence(digits, _PAUSE_NORMAL_MS)
            return _upload_stitched(audio, pid)

        # Fallback: read the amount instead
        amount_key = _format_amount(request.amount).replace(".", "_")
        pid = build_public_id("amounts", amount_key)
        cached = get_cached_url(pid)
        if cached:
            return cached

        keys = amount_to_words(request.amount)
        audio = await _stitch_audio_sequence(keys, _PAUSE_NORMAL_MS)
        return _upload_stitched(audio, pid)

    if request.mode == AudioMode.REPEAT_NUMBER_BOKOO:
        if request.phone_number:
            digits = [ch for ch in request.phone_number if ch.isdigit()]
            pid = build_public_id("phone_bokoo", "".join(digits))
            cached = get_cached_url(pid)
            if cached:
                return cached

            audio = await _stitch_audio_sequence(digits, _PAUSE_BOKOO_MS)
            return _upload_stitched(audio, pid)

        # Fallback: read the amount instead
        amount_key = _format_amount(request.amount).replace(".", "_")
        pid = build_public_id("amounts", amount_key)
        cached = get_cached_url(pid)
        if cached:
            return cached

        keys = amount_to_words(request.amount)
        audio = await _stitch_audio_sequence(keys, _PAUSE_BOKOO_MS)
        return _upload_stitched(audio, pid)

    if request.mode == AudioMode.POLITENESS:
        # Static asset — always the same URL, never changes
        pid = build_public_id("twi", "politeness")
        cached = get_cached_url(pid)
        if cached:
            return cached

        # Try local asset first, upload if needed
        asset = get_asset_audio("twi", "politeness.wav")
        if asset is not None:
            return upload_audio_bytes(asset, pid, file_format="wav")

        # Absolute fallback: generate via TTS API and upload
        audio = await _call_tts_api(_POLITENESS_TEXT)
        return _upload_tts_result(audio, pid)

    raise RuntimeError(f"Unsupported audio mode: {request.mode}")


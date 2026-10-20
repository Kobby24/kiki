"""
Unit tests for composite Twi/English audio synthesis and sentence breakdown.
"""

import io
import math
import struct
import wave
import pytest

from ai.audio_service import (
    synthesize,
    _build_composite_full_audio,
    _stitch_audio_sequence,
    TWI_FRAGMENTS,
)
from ai.schemas import AudioMode, IntentType, SynthesizeAudioRequest


def _create_mock_wav(duration_s: float = 0.5, freq_hz: float = 440.0, sample_rate: int = 22050) -> bytes:
    """Generate a valid 22050Hz mono 16-bit WAV for testing."""
    buf = io.BytesIO()
    n_samples = int(sample_rate * duration_s)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            val = int(16384.0 * math.sin(2.0 * math.pi * freq_hz * i / sample_rate))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(frames)
    return buf.getvalue()


@pytest.fixture(autouse=True)
def mock_tts_api(monkeypatch):
    """Automatically mock remote TTS API in tests to prevent consuming live quota."""
    async def _mock_tts(text: str, bypass_cache: bool = False) -> bytes:
        return _create_mock_wav(duration_s=0.6, freq_hz=350.0)

    monkeypatch.setattr("ai.audio_service._call_tts_api", _mock_tts)
    monkeypatch.setattr("ai.audio_service.set_asset_audio", lambda cat, filename, data: None)


@pytest.mark.asyncio
async def test_composite_audio_withdraw():
    """Test that WITHDRAW composite audio stitches prefix, amount, and MOMO suffix."""
    request = SynthesizeAudioRequest(
        intent=IntentType.WITHDRAW,
        amount=125.50,
        mode=AudioMode.FULL,
    )
    audio_bytes = await _build_composite_full_audio(request)
    assert audio_bytes.startswith(b"RIFF")
    
    with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
        assert wf.getframerate() == 22050
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        duration = wf.getnframes() / wf.getframerate()
        assert 1.0 < duration < 12.0


@pytest.mark.asyncio
async def test_composite_audio_transfer():
    """Test that TRANSFER composite audio includes prefix, amount, koma, phone, and MOMO suffix."""
    request = SynthesizeAudioRequest(
        intent=IntentType.TRANSFER,
        amount=50.0,
        phone_number="0241234567",
        mode=AudioMode.FULL,
    )
    audio_bytes = await _build_composite_full_audio(request)
    assert audio_bytes.startswith(b"RIFF")

    with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
        assert wf.getframerate() == 22050
        duration = wf.getnframes() / wf.getframerate()
        assert 1.5 < duration < 15.0


@pytest.mark.asyncio
async def test_composite_audio_deposit():
    """Test that DEPOSIT composite audio includes prefix, amount, and account suffix."""
    request = SynthesizeAudioRequest(
        intent=IntentType.DEPOSIT,
        amount=200.0,
        mode=AudioMode.FULL,
    )
    audio_bytes = await _build_composite_full_audio(request)
    assert audio_bytes.startswith(b"RIFF")

    with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
        assert wf.getframerate() == 22050
        duration = wf.getnframes() / wf.getframerate()
        assert 1.0 < duration < 10.0


@pytest.mark.asyncio
async def test_synthesize_repeat_amount_returns_url(monkeypatch):
    """Test that REPEAT_AMOUNT mode returns a valid CDN URL."""
    monkeypatch.setattr(
        "ai.audio_service._upload_stitched",
        lambda audio, pid: f"https://res.cloudinary.com/test/video/upload/{pid}.wav"
    )

    request = SynthesizeAudioRequest(
        intent=IntentType.WITHDRAW,
        amount=75.0,
        mode=AudioMode.REPEAT_AMOUNT,
    )
    url = await synthesize(request)
    assert "https://res.cloudinary.com" in url
    assert "sikapa/amounts/75" in url


@pytest.mark.asyncio
async def test_synthesize_full_returns_url(monkeypatch):
    """Test that FULL mode returns a valid CDN URL using composite audio."""
    monkeypatch.setattr(
        "ai.audio_service._upload_stitched",
        lambda audio, pid: f"https://res.cloudinary.com/test/video/upload/{pid}.wav"
    )

    request = SynthesizeAudioRequest(
        intent=IntentType.WITHDRAW,
        amount=100.0,
        mode=AudioMode.FULL,
    )
    url = await synthesize(request)
    assert "https://res.cloudinary.com" in url
    assert "sikapa/full/WITHDRAW_100_none" in url

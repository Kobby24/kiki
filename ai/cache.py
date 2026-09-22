"""
File-based cache for HCI LAB API responses.

Caches ASR transcripts and TTS audio on disk so identical requests
never cost a second API call.  Keyed by SHA-256 hash of the input
(audio bytes for ASR, text string for TTS).

Cache location: ``ai/cache_data/{asr,tts}/``
"""

import hashlib
import json
from pathlib import Path
from typing import Optional

_CACHE_DIR = Path(__file__).parent / "cache_data"
_ASR_DIR = _CACHE_DIR / "asr"
_TTS_DIR = _CACHE_DIR / "tts"
_ASSETS_DIR = Path(__file__).parent / "assets"

# L1 In-Memory Cache for fast O(1) buffer lookup without disk syscalls
_MEM_CACHE: dict[str, bytes] = {}


def _ensure_dirs() -> None:
    """Create cache directories if they don't exist."""
    _ASR_DIR.mkdir(parents=True, exist_ok=True)
    _TTS_DIR.mkdir(parents=True, exist_ok=True)


def _hash_bytes(data: bytes) -> str:
    """SHA-256 hash of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def _hash_text(text: str) -> str:
    """SHA-256 hash of a text string."""
    return _hash_bytes(text.encode("utf-8"))


# --- Named Asset Storage (ai/assets/{category}/{filename}.wav) --- #

def get_asset_audio(category: str, filename: str) -> Optional[bytes]:
    """Retrieve pre-baked audio asset.
    
    Checks in-memory cache first, then disk under ai/assets/{category}/{filename}.
    Returns raw WAV bytes or None if not present.
    """
    key = f"asset:{category}:{filename}"
    if key in _MEM_CACHE:
        return _MEM_CACHE[key]

    path = _ASSETS_DIR / category / filename
    if path.exists():
        data = path.read_bytes()
        _MEM_CACHE[key] = data
        return data
    return None


def set_asset_audio(category: str, filename: str, wav_bytes: bytes) -> None:
    """Store pre-baked audio asset to disk and memory cache."""
    target_dir = _ASSETS_DIR / category
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / filename
    path.write_bytes(wav_bytes)
    _MEM_CACHE[f"asset:{category}:{filename}"] = wav_bytes


# --- ASR Cache --- #

def get_asr_cache(audio_bytes: bytes) -> Optional[str]:
    """Return the cached transcript for *audio_bytes*, or ``None``."""
    _ensure_dirs()
    path = _ASR_DIR / f"{_hash_bytes(audio_bytes)}.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("transcript", "")
    return None


def set_asr_cache(audio_bytes: bytes, transcript: str) -> None:
    """Persist a transcript for *audio_bytes* to disk."""
    _ensure_dirs()
    path = _ASR_DIR / f"{_hash_bytes(audio_bytes)}.json"
    path.write_text(
        json.dumps({"transcript": transcript}, ensure_ascii=False),
        encoding="utf-8",
    )


# --- TTS Request Cache --- #

def get_tts_cache(text: str) -> Optional[bytes]:
    """Return cached WAV bytes for *text*, or ``None``."""
    key = f"tts:{_hash_text(text)}"
    if key in _MEM_CACHE:
        return _MEM_CACHE[key]

    _ensure_dirs()
    path = _TTS_DIR / f"{_hash_text(text)}.wav"
    if path.exists():
        data = path.read_bytes()
        _MEM_CACHE[key] = data
        return data
    return None


def set_tts_cache(text: str, wav_bytes: bytes) -> None:
    """Persist WAV bytes for *text* to disk and L1 memory cache."""
    _ensure_dirs()
    key = f"tts:{_hash_text(text)}"
    _MEM_CACHE[key] = wav_bytes
    path = _TTS_DIR / f"{_hash_text(text)}.wav"
    path.write_bytes(wav_bytes)


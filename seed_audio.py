"""
Pre-deployment Audio Seeding Utility for Sikapa AI.

Pre-generates and caches all static audio assets (pure Twi sentence fragments,
politeness, conversational responses, and English amount components) so that
production requests execute with sub-millisecond local latency.

Features:
- Modular seeding: run piece-by-piece (--piece fragments|politeness|conversational|digits|cloudinary)
- Automatic skip: checks if a file already exists on disk; skips without consuming any API quota
- Quota ceiling: stops cleanly after --limit N API calls and outputs the exact command to resume
- Cloudinary integration: push seeded assets to Cloudinary with --cloudinary
- Offline / Mock mode: generate synthetic WAVs for testing/CI without an API key (--mock)

Usage Examples:
    # Seed the 5 core Twi fragments with a strict limit of 2 calls:
    python ai/scripts/seed_audio.py --piece fragments --limit 2

    # Run the same command again - it will skip the 2 completed and do the next ones!
    python ai/scripts/seed_audio.py --piece fragments --limit 2

    # Seed all Twi fragments and sync to Cloudinary:
    python ai/scripts/seed_audio.py --piece fragments --cloudinary

    # Dry-run with mock audio (0 API calls, no key needed):
    python ai/scripts/seed_audio.py --mock
"""

import argparse
import asyncio
import io
import math
import os
import struct
import sys
import wave
from pathlib import Path

# Ensure UTF-8 output on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure project root is in sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from ai.cache import (
    get_asset_audio,
    set_asset_audio,
)
from ai.ai_config import get_ai_settings
from ai.audio_service import (
    _call_tts_api,
    _DIGIT_WORDS,
    _POLITENESS_TEXT,
    TWI_FRAGMENTS,
)
from ai.cloudinary_storage import upload_local_file

# Static Twi conversational phrases (for UI confirmation / prompts)
_CONVERSATIONAL_PHRASES: dict[str, str] = {
    "cashout_allowed": "Mayɛ ho kwan sɛ megye sika wɔ me MoMo mu.",
    "withdraw_request": "Mepɛ sɛ megye sika.",
    "repeat_again": "Ma menka no bio mma wo.",
    "confirm_yes": "Aane, ɛyɛ saa.",
    "confirm_no": "Daabi, ɛnyɛ saa.",
    "thank_you": "Meda wo ase pii.",
}

# Assets root directory
_ASSETS_DIR = _PROJECT_ROOT / "ai" / "assets"


class QuotaTracker:
    """Tracks and enforces a strict ceiling on remote API calls."""

    def __init__(self, limit: int | None):
        self.limit = limit
        self.calls_made = 0
        self.skipped = 0

    def can_call(self) -> bool:
        if self.limit is None:
            return True
        return self.calls_made < self.limit

    def record_call(self) -> None:
        self.calls_made += 1

    def record_skip(self) -> None:
        self.skipped += 1


def _create_mock_wav(duration_s: float = 0.5, freq_hz: float = 440.0, sample_rate: int = 22050) -> bytes:
    """Generate a clean synthetic sine-wave WAV file using only stdlib."""
    buf = io.BytesIO()
    n_samples = int(sample_rate * duration_s)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            val = int(16384.0 * math.sin(2.0 * math.pi * freq_hz * i / sample_rate))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(frames)
    return buf.getvalue()


def _is_valid_audio(data: bytes | None) -> bool:
    """Return True if the data is a non-empty audio clip (> 500 bytes)."""
    return data is not None and len(data) > 500


async def seed_fragments(tracker: QuotaTracker, mock: bool = False, force: bool = False) -> int:
    """Pre-generate the pure Twi sentence fragments into ai/assets/twi/."""
    print(f"\n[Piece: Twi Fragments] Checking {len(TWI_FRAGMENTS)} sentence fragments in ai/assets/twi/ ...")
    count = 0
    for key, text in TWI_FRAGMENTS.items():
        filename = f"{key}.wav"
        existing = get_asset_audio("twi", filename)

        if _is_valid_audio(existing) and not force:
            print(f"  ⏩ [SKIPPED] '{key}' already exists ({len(existing):,} bytes) -> 0 API calls used")
            tracker.record_skip()
            count += 1
            continue

        if not mock and not tracker.can_call():
            print(f"  ⏸ Quota limit of {tracker.limit} calls reached. Pausing at '{key}'.")
            return count

        if mock:
            wav_bytes = _create_mock_wav(duration_s=0.8, freq_hz=350.0 + count * 30)
            print(f"  ⚙️ [MOCK] Generated synthetic WAV for '{key}'")
        else:
            print(f"  🎙️ Calling HCI LAB TTS for '{key}' ('{text}')... [Call #{tracker.calls_made + 1}]")
            try:
                wav_bytes = await _call_tts_api(text, bypass_cache=force)
                tracker.record_call()
            except Exception as exc:
                print(f"  ❌ Failed for '{key}': {exc}")
                if "quota" in str(exc).lower():
                    print("  ⚠️ HCI LAB quota limit reached. Halting seeding to conserve quota.")
                return count

        set_asset_audio("twi", filename, wav_bytes)
        print(f"  ✅ Saved ai/assets/twi/{filename} ({len(wav_bytes):,} bytes)")
        count += 1

    return count


async def seed_politeness(tracker: QuotaTracker, mock: bool = False, force: bool = False) -> int:
    """Pre-generate politeness audio into ai/assets/twi/."""
    print("\n[Piece: Politeness] Checking politeness phrase in ai/assets/twi/ ...")
    filename = "politeness.wav"
    existing = get_asset_audio("twi", filename)

    if _is_valid_audio(existing) and not force:
        print(f"  ⏩ [SKIPPED] Politeness already exists ({len(existing):,} bytes) -> 0 API calls used")
        tracker.record_skip()
        return 1

    if not mock and not tracker.can_call():
        print(f"  ⏸ Quota limit of {tracker.limit} calls reached. Skipping politeness.")
        return 0

    if mock:
        wav_bytes = _create_mock_wav(duration_s=1.2, freq_hz=380.0)
    else:
        print(f"  🎙️ Calling HCI LAB TTS for politeness... [Call #{tracker.calls_made + 1}]")
        try:
            wav_bytes = await _call_tts_api(_POLITENESS_TEXT, bypass_cache=force)
            tracker.record_call()
        except Exception as exc:
            print(f"  ❌ Failed for politeness: {exc}")
            return 0

    set_asset_audio("twi", filename, wav_bytes)
    print(f"  ✅ Saved ai/assets/twi/{filename} ({len(wav_bytes):,} bytes)")
    return 1


async def seed_conversational(tracker: QuotaTracker, mock: bool = False, force: bool = False) -> int:
    """Pre-generate static Twi conversational phrases into ai/assets/twi/."""
    total = len(_CONVERSATIONAL_PHRASES)
    print(f"\n[Piece: Conversational] Checking {total} conversational phrases in ai/assets/twi/ ...")
    count = 0
    for key, text in _CONVERSATIONAL_PHRASES.items():
        filename = f"{key}.wav"
        existing = get_asset_audio("twi", filename)

        if _is_valid_audio(existing) and not force:
            print(f"  ⏩ [SKIPPED] '{key}' already exists ({len(existing):,} bytes) -> 0 API calls used")
            tracker.record_skip()
            count += 1
            continue

        if not mock and not tracker.can_call():
            print(f"  ⏸ Quota limit of {tracker.limit} calls reached. Pausing at '{key}'.")
            return count

        if mock:
            wav_bytes = _create_mock_wav(duration_s=1.0, freq_hz=400.0 + count * 20)
        else:
            print(f"  🎙️ Calling HCI LAB TTS for '{key}' ('{text[:45]}...')... [Call #{tracker.calls_made + 1}]")
            try:
                wav_bytes = await _call_tts_api(text, bypass_cache=force)
                tracker.record_call()
            except Exception as exc:
                print(f"  ❌ Failed for '{key}': {exc}")
                return count

        set_asset_audio("twi", filename, wav_bytes)
        print(f"  ✅ Saved ai/assets/twi/{filename} ({len(wav_bytes):,} bytes)")
        count += 1

    return count


async def seed_digits(tracker: QuotaTracker, mock: bool = False, force: bool = False) -> int:
    """Ensure all digits and amount assets exist in ai/assets/en_digits/."""
    print("\n[Piece: English Digits & Amounts] Checking ai/assets/en_digits/ ...")
    digits_dir = _ASSETS_DIR / "en_digits"
    digits_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for digit, word in _DIGIT_WORDS.items():
        filename = f"{digit}.wav"
        existing = get_asset_audio("en_digits", filename)

        if _is_valid_audio(existing) and not force:
            print(f"  ⏩ [SKIPPED] Digit '{digit}' ({word}) already exists ({len(existing):,} bytes)")
            tracker.record_skip()
            count += 1
            continue

        if not mock and not tracker.can_call():
            print(f"  ⏸ Quota limit reached. Skipping digit {digit}.")
            continue

        if mock:
            wav_bytes = _create_mock_wav(duration_s=0.35, freq_hz=300 + int(digit) * 40)
        else:
            print(f"  🎙️ Calling TTS API for digit {digit} ('{word}')... [Call #{tracker.calls_made + 1}]")
            try:
                wav_bytes = await _call_tts_api(word, bypass_cache=force)
                tracker.record_call()
            except Exception as exc:
                print(f"  ❌ Failed for digit {digit}: {exc}")
                return count

        set_asset_audio("en_digits", filename, wav_bytes)
        print(f"  ✅ Saved ai/assets/en_digits/{filename}")
        count += 1

    return count


def sync_to_cloudinary() -> tuple[int, int]:
    """Upload all seeded audio files from ai/assets/ to Cloudinary."""
    print("\n[Piece: Cloudinary Sync] Uploading all audio assets to Cloudinary CDN ...")
    uploaded = 0
    errors = 0

    for category_dir in sorted(_ASSETS_DIR.iterdir()):
        if not category_dir.is_dir():
            continue

        folder = category_dir.name
        files = sorted(
            f for f in category_dir.iterdir()
            if f.is_file() and f.suffix.lower() in {".wav", ".mp3"}
        )

        for audio_file in files:
            try:
                url = upload_local_file(audio_file, folder)
                print(f"  ☁️ OK: {folder}/{audio_file.name} -> {url}")
                uploaded += 1
            except Exception as exc:
                print(f"  ❌ FAIL: {folder}/{audio_file.name} -> {exc}")
                errors += 1

    return uploaded, errors


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pre-generate static audio assets for Sikapa AI in pieces with resource conservation."
    )
    parser.add_argument(
        "--piece",
        choices=["all", "fragments", "politeness", "conversational", "digits", "cloudinary"],
        default="all",
        help="Select which piece to seed: 'fragments' (5 Twi clauses), 'politeness', 'conversational', 'digits', 'cloudinary', or 'all'.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Strict maximum number of live API calls to make in this run.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-generation of files even if they already exist on disk.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Generate synthetic sine-wave WAV assets (0 API calls, no key needed).",
    )
    parser.add_argument(
        "--cloudinary",
        action="store_true",
        help="Automatically sync all generated assets to Cloudinary after seeding.",
    )
    args = parser.parse_args()

    settings = get_ai_settings()
    is_mock = args.mock or not bool(settings.hci_lab_api_key)

    tracker = QuotaTracker(limit=args.limit)

    print("=" * 65)
    print("🎙️ SIKAPA AUDIO SEEDING ENGINE")
    print(f"   Target piece : {args.piece}")
    print(f"   API Limit    : {args.limit if args.limit is not None else 'Unlimited'}")
    print(f"   Force mode   : {args.force}")
    print(f"   Execution    : {'MOCK (Offline)' if is_mock else 'LIVE HCI LAB API'}")
    print("=" * 65)

    piece = args.piece
    do_all = piece == "all"

    # 1. Core Sentence Fragments (highest priority for composite synthesis)
    if do_all or piece == "fragments":
        await seed_fragments(tracker, mock=is_mock, force=args.force)

    # 2. Politeness Audio
    if do_all or piece == "politeness":
        await seed_politeness(tracker, mock=is_mock, force=args.force)

    # 3. Conversational Phrases
    if do_all or piece == "conversational":
        await seed_conversational(tracker, mock=is_mock, force=args.force)

    # 4. English Digits
    if do_all or piece == "digits":
        await seed_digits(tracker, mock=is_mock, force=args.force)

    # 5. Cloudinary upload
    if args.cloudinary or piece == "cloudinary":
        sync_to_cloudinary()

    print("\n" + "=" * 65)
    print("🏁 SEEDING RUN COMPLETE")
    print(f"   API calls made this run : {tracker.calls_made}")
    print(f"   Items skipped (existing): {tracker.skipped}")

    if tracker.limit is not None and tracker.calls_made >= tracker.limit:
        print("\n💡 PAUSED: You reached your quota limit for this run.")
        print("   To continue with the next piece, simply run:")
        print(f"       python ai/scripts/seed_audio.py --piece {piece} --limit {tracker.limit}")
        print("   The system will automatically skip already-completed files!")
    else:
        print("\n✨ All requested audio components are seeded and ready!")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())

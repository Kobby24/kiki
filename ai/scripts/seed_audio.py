"""
Pre-deployment Audio Seeding Utility for Sikapa AI.

Pre-generates and caches all static audio assets (digits 0-9, politeness,
and common cash-out amounts) so that production requests never call the
remote TTS API and execute with sub-millisecond local latency.

Usage:
    # Generate using live HCI LAB TTS API with a strict quota limit (e.g. 5 calls):
    python ai/scripts/seed_audio.py --limit 5

    # Force overwrite existing mock files with real API calls up to limit:
    python ai/scripts/seed_audio.py --limit 5 --force

    # Generate offline synthetic WAV assets for offline testing/CI without API key:
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
    get_tts_cache,
    set_asset_audio,
    set_tts_cache,
)
from ai.ai_config import get_ai_settings
from ai.audio_service import _call_tts_api, _DIGIT_WORDS, _POLITENESS_TEXT

# Static Twi conversational phrases (no dynamic placeholders)
_CONVERSATIONAL_PHRASES: dict[str, str] = {
    "cashout_allowed": "Mayɛ ho kwan sɛ megye sika wɔ me MoMo mu.",
    "withdraw_request": "Mepɛ sɛ megye sika.",
    "repeat_again": "Ma menka no bio mma wo.",
    "confirm_yes": "Aane, ɛyɛ saa.",
    "confirm_no": "Daabi, ɛnyɛ saa.",
    "thank_you": "Meda wo ase pii.",
}

# Standard common cashout amounts (GHS)
_COMMON_AMOUNTS = [5, 10, 20, 50, 100, 200, 500]


class QuotaTracker:
    """Tracks and enforces a strict ceiling on remote API calls."""

    def __init__(self, limit: int | None):
        self.limit = limit
        self.calls_made = 0

    def can_call(self) -> bool:
        if self.limit is None:
            return True
        return self.calls_made < self.limit

    def record_call(self) -> None:
        self.calls_made += 1


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


async def seed_digits(tracker: QuotaTracker, mock: bool = False, force: bool = False) -> int:
    """Pre-generate digits 0-9 into ai/assets/en_digits/."""
    print("\n[1/3] Seeding digits 0-9 into ai/assets/en_digits/ ...")
    count = 0
    for digit, word in _DIGIT_WORDS.items():
        filename = f"{digit}.wav"
        existing = get_asset_audio("en_digits", filename)
        if existing and not force:
            print(f"  - Digit {digit} ('{word}'): already present ({len(existing)} bytes)")
            count += 1
            continue

        if not mock and not tracker.can_call():
            print(f"  ⏸ Quota limit of {tracker.limit} calls reached. Skipping digit {digit}.")
            continue

        if mock:
            wav_bytes = _create_mock_wav(duration_s=0.35, freq_hz=300 + int(digit) * 40)
        else:
            print(f"  - Calling TTS API for digit {digit} ('{word}')... (Call #{tracker.calls_made + 1}, waiting for model...)")
            try:
                wav_bytes = await _call_tts_api(word, bypass_cache=force)
                tracker.record_call()
            except Exception as exc:
                print(f"  ❌ Failed for digit {digit}: {exc}")
                if "quota" in str(exc).lower():
                    print("  ⚠️ HCI LAB quota limit reached. Halting seeding to conserve quota.")
                elif "timed out" in str(exc).lower():
                    print("  ⚠️ Model timed out. Halting run to prevent repeated delays.")
                return count

        set_asset_audio("en_digits", filename, wav_bytes)
        print(f"  ✓ Saved ai/assets/en_digits/{filename} ({len(wav_bytes)} bytes)")
        count += 1
    return count


async def seed_politeness(tracker: QuotaTracker, mock: bool = False, force: bool = False) -> None:
    """Pre-generate politeness audio into ai/assets/twi/."""
    print("\n[2/3] Seeding politeness into ai/assets/twi/ ...")
    filename = "politeness.wav"
    existing = get_asset_audio("twi", filename)
    if existing and not force:
        print(f"  - Politeness: already present ({len(existing)} bytes)")
        return

    if not mock and not tracker.can_call():
        print(f"  ⏸ Quota limit of {tracker.limit} calls reached. Skipping politeness.")
        return

    if mock:
        wav_bytes = _create_mock_wav(duration_s=1.2, freq_hz=380.0)
    else:
        print(f"  - Calling TTS API for politeness... (Call #{tracker.calls_made + 1}, waiting for model...)")
        try:
            wav_bytes = await _call_tts_api(_POLITENESS_TEXT, bypass_cache=force)
            tracker.record_call()
        except Exception as exc:
            print(f"  ❌ Failed for politeness: {exc}")
            if "quota" in str(exc).lower():
                print("  ⚠️ HCI LAB quota limit reached. Halting seeding to conserve quota.")
            return

    set_asset_audio("twi", filename, wav_bytes)
    print(f"  ✓ Saved ai/assets/twi/{filename} ({len(wav_bytes)} bytes)")


async def seed_conversational(tracker: QuotaTracker, mock: bool = False, force: bool = False) -> int:
    """Pre-generate static Twi conversational phrases into ai/assets/twi/."""
    total = len(_CONVERSATIONAL_PHRASES)
    print(f"\n[2.5/3] Seeding {total} conversational phrases into ai/assets/twi/ ...")
    count = 0
    for key, text in _CONVERSATIONAL_PHRASES.items():
        filename = f"{key}.wav"
        existing = get_asset_audio("twi", filename)
        if existing and not force:
            print(f"  - {key}: already present ({len(existing)} bytes)")
            count += 1
            continue

        if not mock and not tracker.can_call():
            print(f"  ⏸ Quota limit of {tracker.limit} calls reached. Skipping {key}.")
            continue

        if mock:
            wav_bytes = _create_mock_wav(duration_s=1.5, freq_hz=400.0)
        else:
            print(f"  - Calling TTS API for {key} ('{text[:50]}')... (Call #{tracker.calls_made + 1}, waiting for model...)")
            try:
                wav_bytes = await _call_tts_api(text, bypass_cache=force)
                tracker.record_call()
            except Exception as exc:
                print(f"  ❌ Failed for {key}: {exc}")
                if "quota" in str(exc).lower():
                    print("  ⚠️ HCI LAB quota limit reached. Halting seeding to conserve quota.")
                elif "timed out" in str(exc).lower():
                    print("  ⚠️ Model timed out. Halting run to prevent repeated delays.")
                return count

        set_asset_audio("twi", filename, wav_bytes)
        print(f"  ✓ Saved ai/assets/twi/{filename} ({len(wav_bytes)} bytes)")
        count += 1
    return count


async def seed_common_cashouts(tracker: QuotaTracker, mock: bool = False, force: bool = False) -> int:
    """Pre-generate common cash-out full utterances into disk cache."""
    print("\n[3/3] Seeding common cashout utterances into TTS cache ...")
    count = 0
    for amount in _COMMON_AMOUNTS:
        text = f"Mepa wo kyɛw, mepɛ sɛ megye GHS {amount} fi me Mobile Money so."
        cached = get_tts_cache(text)
        if cached and not force:
            print(f"  - GHS {amount}: already present ({len(cached)} bytes)")
            count += 1
            continue

        if not mock and not tracker.can_call():
            print(f"  ⏸ Quota limit of {tracker.limit} calls reached. Skipping GHS {amount}.")
            continue

        if mock:
            wav_bytes = _create_mock_wav(duration_s=2.0, freq_hz=440.0)
        else:
            print(f"  - Calling TTS API for GHS {amount}... (Call #{tracker.calls_made + 1}, waiting for model...)")
            try:
                wav_bytes = await _call_tts_api(text, bypass_cache=force)
                tracker.record_call()
            except Exception as exc:
                print(f"  ❌ Failed for GHS {amount}: {exc}")
                if "quota" in str(exc).lower():
                    print("  ⚠️ HCI LAB quota limit reached. Halting seeding to conserve quota.")
                elif "timed out" in str(exc).lower():
                    print("  ⚠️ Model timed out. Halting run to prevent repeated delays.")
                return count

        set_tts_cache(text, wav_bytes)
        print(f"  ✓ Cached audio for GHS {amount} ({len(wav_bytes)} bytes)")
        count += 1
    return count


async def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-generate static audio assets for Sikapa.")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Generate synthetic sine-wave WAV files without calling the remote TTS API.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Strict ceiling on the maximum number of live API calls to make in this run.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite existing cached/mock files up to the call limit.",
    )
    parser.add_argument(
        "--skip-digits",
        action="store_true",
        help="Skip seeding English digits, focusing strictly on Twi phrases.",
    )
    parser.add_argument(
        "--only",
        choices=["all", "twi", "digits", "politeness", "conversational", "cashouts"],
        default="all",
        help="Selectively seed: 'twi' (politeness + conversational + cashouts), 'conversational', 'politeness', 'cashouts', 'digits', or 'all'.",
    )
    args = parser.parse_args()

    settings = get_ai_settings()
    is_mock = args.mock or not bool(settings.hci_lab_api_key)

    tracker = QuotaTracker(limit=args.limit)

    if is_mock and not args.mock:
        print("Notice: No HCI_LAB_API_KEY detected in .env. Running in --mock synthetic mode.")
    elif is_mock:
        print("Running in --mock synthetic mode (0 API calls).")
    else:
        limit_msg = f"up to {args.limit} calls" if args.limit is not None else "unlimited calls"
        print(f"Running in LIVE mode with HCI LAB TTS API ({limit_msg}). Target: {args.only}")

    do_all = args.only == "all"
    is_twi = args.only == "twi"
    digits_count = 0
    conversational_count = 0
    cashouts_count = 0

    # 1. Prioritize Twi Politeness Audio
    if do_all or is_twi or args.only == "politeness":
        await seed_politeness(tracker, mock=is_mock, force=args.force)

    # 2. Conversational Twi phrases
    if do_all or is_twi or args.only == "conversational":
        conversational_count = await seed_conversational(tracker, mock=is_mock, force=args.force)

    # 3. Prioritize Twi Common Cashouts
    if do_all or is_twi or args.only == "cashouts":
        cashouts_count = await seed_common_cashouts(tracker, mock=is_mock, force=args.force)

    # 4. English Digits (skipped if --skip-digits or --only twi)
    if not args.skip_digits and (do_all or args.only == "digits"):
        digits_count = await seed_digits(tracker, mock=is_mock, force=args.force)

    print("\n" + "=" * 50)
    print("✅ Pre-deployment audio seeding run finished!")
    print(f"   API calls made this run: {tracker.calls_made}" + (f" (capped at {args.limit})" if args.limit is not None else ""))
    print(f"   Phrases ready: Politeness in ai/assets/twi/politeness.wav")
    print(f"   Conversational: {conversational_count}/{len(_CONVERSATIONAL_PHRASES)} phrases in ai/assets/twi/")
    print(f"   Utterances ready: {cashouts_count} amounts pre-cached")
    print(f"   Digits ready: {digits_count} in ai/assets/en_digits/")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())

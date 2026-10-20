"""
Interactive CLI script to test digit-by-digit number stitching.

Prompts the user for a phone number or digit string, loads pre-baked
digit audio from ai/assets/en_digits/, stitches them with configurable
rhythm pauses, and writes the playable audio output file.
"""

import asyncio
import os
import sys
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

from ai.audio_service import (
    _stitch_audio_sequence,
    _PAUSE_NORMAL_MS,
    _PAUSE_BOKOO_MS,
)
from ai.amount_builder import amount_to_words

ASSETS_DIR = _PROJECT_ROOT / "ai" / "assets" / "en_digits"
OUTPUT_FILE = _PROJECT_ROOT / "stitched_number_test.mp3"

_AMOUNT_ASSET_KEYS = ["0", "cedis", "pesewas", "hundred", "thousand", "million", "and", "point"]


def check_available_digits() -> dict[str, Path]:
    """Verify which digit assets are present in ai/assets/en_digits/."""
    available = {}
    for d in range(10):
        ch = str(d)
        p = ASSETS_DIR / f"{ch}.wav"
        if p.exists() and p.stat().st_size > 0:
            available[ch] = p
    return available


def _check_amount_assets() -> bool:
    """Verify amount-related assets exist (cedis, pesewas, magnitudes, etc.)."""
    missing = []
    for key in _AMOUNT_ASSET_KEYS + [str(d) for d in range(10)]:
        p = ASSETS_DIR / f"{key}.wav"
        if not p.exists() or p.stat().st_size == 0:
            missing.append(key)
    return missing


def main() -> None:
    print("=" * 60)
    print("📞 Sikapa Number Combination & Audio Stitching Test")
    print("   (Testing production engine from ai/audio_service.py)")
    print("=" * 60)

    # 1. Verify assets
    available = check_available_digits()
    print(f"\n📂 Checking audio assets in: {ASSETS_DIR}")
    for d in range(10):
        ch = str(d)
        if ch in available:
            size_kb = available[ch].stat().st_size / 1024
            print(f"   ✓ Digit {ch}: {available[ch].name} ({size_kb:.1f} KB)")
        else:
            print(f"   ❌ Digit {ch}: MISSING")

    missing_amount = _check_amount_assets()
    if missing_amount:
        print(f"\n⚠️ Warning: Missing amount assets: {', '.join(missing_amount)}")
    else:
        print("   ✅ All amount assets (cedis, pesewas, magnitudes, digits) present!")

    if len(available) < 10:
        missing = [str(d) for d in range(10) if str(d) not in available]
        print(f"\n⚠️ Warning: Missing digits: {', '.join(missing)}")
    else:
        print("   ✅ All 10 digits (0-9) are present and ready!")

    print("-" * 60)

    # 2. Choose test mode
    print("\nSelect test mode:")
    print("  [1] Phone number / digit sequence (with pauses)")
    print("  [2] Amount combination (gapless, e.g. 125.50 -> 125 cedis and 50 pesewas)")
    mode_choice = input("Choice [default 1]: ").strip()

    if mode_choice == "2":
        try:
            amount_input = input("\nEnter amount (e.g. 125.50, 20, 0.50): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            return

        try:
            amount = float(amount_input)
        except ValueError:
            print("❌ Error: Invalid amount.")
            return

        keys = amount_to_words(amount)
        print(f"🔢 Amount keys: {' '.join(keys)}")

        # Amount mode is gapless (pause=0), matching REPEAT_AMOUNT in production
        pause_ms = 0
        cadence_name = "Amount (gapless)"

        try:
            stitched_data = asyncio.run(_stitch_audio_sequence(keys, pause_ms))
        except Exception as e:
            print(f"\n❌ Stitching failed via audio_service: {e}")
            return

        OUTPUT_FILE = _PROJECT_ROOT / "stitched_amount_test.mp3"
    else:
        # 3. Prompt for phone number input
        try:
            user_input = input("\nEnter phone number or digit sequence (e.g. 0244123456): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            return

        digits = [ch for ch in user_input if ch.isdigit()]
        if not digits:
            print("❌ Error: No valid digits found in input.")
            return

        print(f"🔢 Interpreted digits: {' '.join(digits)} (length: {len(digits)})")

        # 4. Choose playback cadence (using actual production constants)
        print("\nSelect playback cadence:")
        print(f"  [1] Normal ({_PAUSE_NORMAL_MS}ms fast natural conversational flow)")
        print(f"  [2] Bokoo / Slow ({_PAUSE_BOKOO_MS}ms deliberate accessibility pause)")
        print("  [3] Custom pause duration (enter any number of milliseconds)")
        cadence_choice = input("Choice [default 1]: ").strip()

        if cadence_choice == "2":
            pause_ms = _PAUSE_BOKOO_MS
            cadence_name = f"Bokoo / Slow ({pause_ms}ms)"
        elif cadence_choice == "3":
            custom = input("Enter pause duration in ms (e.g. 80): ").strip()
            pause_ms = int(custom) if custom.isdigit() else _PAUSE_NORMAL_MS
            cadence_name = f"Custom ({pause_ms}ms)"
        else:
            pause_ms = _PAUSE_NORMAL_MS
            cadence_name = f"Normal ({pause_ms}ms)"

        print(f"⏱ Using cadence: {cadence_name}")

        # 5. Stitch audio using PRODUCTION engine
        try:
            stitched_data = asyncio.run(_stitch_audio_sequence(digits, pause_ms))
        except Exception as e:
            print(f"\n❌ Stitching failed via audio_service: {e}")
            return

        OUTPUT_FILE = _PROJECT_ROOT / "stitched_number_test.mp3"

    # 6. Write output file
    OUTPUT_FILE.write_bytes(stitched_data)
    size_kb = len(stitched_data) / 1024

    print("\n" + "=" * 60)
    print("✅ Stitched audio successfully generated via production engine!")
    print(f"   Output file: {OUTPUT_FILE}")
    print(f"   Total size:  {size_kb:.1f} KB")
    print("=" * 60)

    # 7. Offer to play audio
    play_choice = input("\nWould you like to play the audio now? (Y/n): ").strip().lower()
    if play_choice in ("", "y", "yes"):
        try:
            if sys.platform == "win32":
                os.startfile(str(OUTPUT_FILE))
                print("▶️ Playing audio in your default media player...")
            else:
                print(f"Open this file to listen: {OUTPUT_FILE}")
        except Exception as e:
            print(f"Could not open media player automatically: {e}")
            print(f"You can listen to the file directly at: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

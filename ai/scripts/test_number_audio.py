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
    _stitch_digit_audio,
    _PAUSE_NORMAL_MS,
    _PAUSE_BOKOO_MS,
)

ASSETS_DIR = _PROJECT_ROOT / "ai" / "assets" / "en_digits"
OUTPUT_FILE = _PROJECT_ROOT / "stitched_number_test.mp3"


def check_available_digits() -> dict[str, Path]:
    """Verify which digit assets are present in ai/assets/en_digits/."""
    available = {}
    for d in range(10):
        ch = str(d)
        p = ASSETS_DIR / f"{ch}.wav"
        if p.exists() and p.stat().st_size > 0:
            available[ch] = p
    return available


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

    if len(available) < 10:
        missing = [str(d) for d in range(10) if str(d) not in available]
        print(f"\n⚠️ Warning: Missing digits: {', '.join(missing)}")
    else:
        print("   ✅ All 10 digits (0-9) are present and ready!")

    print("-" * 60)

    # 2. Prompt for user input
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

    # 3. Choose playback cadence (using actual production constants)
    print("\nSelect playback cadence:")
    print(f"  [1] Normal ({_PAUSE_NORMAL_MS}ms fast natural conversational flow)")
    print(f"  [2] Bokoo / Slow ({_PAUSE_BOKOO_MS}ms deliberate accessibility pause)")
    print("  [3] Custom pause duration (enter any number of milliseconds)")
    mode_choice = input("Choice [default 1]: ").strip()

    if mode_choice == "2":
        pause_ms = _PAUSE_BOKOO_MS
        cadence_name = f"Bokoo / Slow ({pause_ms}ms)"
    elif mode_choice == "3":
        custom = input("Enter pause duration in ms (e.g. 80): ").strip()
        pause_ms = int(custom) if custom.isdigit() else _PAUSE_NORMAL_MS
        cadence_name = f"Custom ({pause_ms}ms)"
    else:
        pause_ms = _PAUSE_NORMAL_MS
        cadence_name = f"Normal ({pause_ms}ms)"

    print(f"⏱ Using cadence: {cadence_name}")

    # 4. Stitch audio using PRODUCTION engine
    try:
        stitched_data = asyncio.run(_stitch_digit_audio(user_input, pause_ms))
    except Exception as e:
        print(f"\n❌ Stitching failed via audio_service: {e}")
        return

    # 5. Write output file
    OUTPUT_FILE.write_bytes(stitched_data)
    size_kb = len(stitched_data) / 1024

    print("\n" + "=" * 60)
    print("✅ Stitched audio successfully generated via production engine!")
    print(f"   Output file: {OUTPUT_FILE}")
    print(f"   Total size:  {size_kb:.1f} KB")
    print("=" * 60)

    # 6. Offer to play audio
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

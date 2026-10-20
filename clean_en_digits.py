"""
Utility script to ensure all English digits and amount words in ai/assets/en_digits/
are converted to standard 22050Hz 16-bit mono PCM WAV files and trimmed of silence.

This eliminates awkward pauses and ensures fast, natural-sounding playback.
"""

import struct
import wave
from pathlib import Path

import miniaudio

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "en_digits"


def clean_and_trim_all(threshold: int = 300, lead_tail_ms: int = 25) -> int:
    """Trim silence and normalize all assets in en_digits to 22050Hz 16-bit mono WAV."""
    if not ASSETS_DIR.exists():
        print(f"Directory not found: {ASSETS_DIR}")
        return 0

    wav_files = sorted(ASSETS_DIR.glob("*.wav"))
    converted = 0

    for p in wav_files:
        with open(p, "rb") as f:
            raw_bytes = f.read()

        # Check if already a clean trimmed WAV
        if raw_bytes.startswith(b"RIFF"):
            try:
                with wave.open(str(p), "rb") as w:
                    # If it's already 22050Hz mono and short (< 1.2s), check if trimming is needed
                    if w.getframerate() == 22050 and w.getnchannels() == 1 and w.getnframes() < 22050 * 1.2:
                        continue
            except Exception:
                pass

        try:
            decoded = miniaudio.decode(
                raw_bytes,
                nchannels=1,
                sample_rate=22050,
                dither=miniaudio.DitherMode.NONE,
            )
            samples = decoded.samples

            lead_tail_samples = int(22050 * lead_tail_ms / 1000)
            start = 0
            for i, s in enumerate(samples):
                if abs(s) > threshold:
                    start = max(0, i - lead_tail_samples)
                    break

            end = len(samples)
            for i in range(len(samples) - 1, -1, -1):
                if abs(samples[i]) > threshold:
                    end = min(len(samples), i + lead_tail_samples)
                    break

            trimmed = samples[start:end]
            pcm_buf = bytearray()
            for s in trimmed:
                pcm_buf.extend(struct.pack("<h", s))

            with wave.open(str(p), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(22050)
                wf.writeframes(pcm_buf)

            print(f"  ✓ Cleaned {p.name}: {len(samples)/22050:.2f}s -> {len(trimmed)/22050:.2f}s ({len(pcm_buf)+44} bytes)")
            converted += 1
        except Exception as exc:
            print(f"  ❌ Error processing {p.name}: {exc}")

    print(f"\nDone! Processed {len(wav_files)} files ({converted} updated).")
    return converted


if __name__ == "__main__":
    clean_and_trim_all()

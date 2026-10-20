"""
One-time script to upload all pre-baked audio assets to Cloudinary.

Walks the ``ai/assets/`` directory tree and uploads every audio file
(WAV and MP3) to Cloudinary under the ``sikapa/`` namespace.

Usage:
    python ai/scripts/seed_cloudinary.py

Run this once after setting up your Cloudinary credentials in ``.env``,
or whenever you add new pre-baked audio assets to the repository.
"""

import sys
from pathlib import Path

# Ensure the project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ai.cloudinary_storage import upload_local_file

# Root directory containing all pre-baked audio assets
_ASSETS_ROOT = Path(__file__).resolve().parent.parent / "assets"

# Audio file extensions to upload
_AUDIO_EXTENSIONS = {".wav", ".mp3"}


def main() -> None:
    """Walk all asset subdirectories and upload each audio file."""
    if not _ASSETS_ROOT.exists():
        print(f"Assets directory not found: {_ASSETS_ROOT}")
        sys.exit(1)

    uploaded = 0
    errors = 0

    # Each subdirectory under ai/assets/ becomes a Cloudinary folder
    # e.g. ai/assets/en_digits/ -> sikapa/en_digits/
    #      ai/assets/twi/       -> sikapa/twi/
    for category_dir in sorted(_ASSETS_ROOT.iterdir()):
        if not category_dir.is_dir():
            continue

        folder = category_dir.name
        files = sorted(
            f for f in category_dir.iterdir()
            if f.is_file() and f.suffix.lower() in _AUDIO_EXTENSIONS
        )

        if not files:
            continue

        print(f"\n[{folder}] Uploading {len(files)} files...")

        for audio_file in files:
            try:
                url = upload_local_file(audio_file, folder)
                print(f"  OK  {audio_file.name} -> {url}")
                uploaded += 1
            except Exception as exc:
                print(f"  FAIL {audio_file.name} -> {exc}")
                errors += 1

    # Summary
    print("\n" + "=" * 60)
    print(f"Cloudinary seeding complete.")
    print(f"  Uploaded: {uploaded}")
    print(f"  Errors:   {errors}")

    if errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

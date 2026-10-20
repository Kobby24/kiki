"""
Cloudinary audio storage service for the Sikapa AI engine.

Handles uploading audio files (both local assets and dynamically stitched
clips) to Cloudinary's CDN. All audio is stored under the ``sikapa/``
folder namespace with deterministic public IDs for cache-friendly retrieval.

Cloudinary treats audio as ``resource_type="video"`` internally.
"""

import io
import logging
import tempfile
from pathlib import Path
from typing import Optional

import cloudinary
import cloudinary.uploader
import cloudinary.api

from ai.ai_config import get_ai_settings

logger = logging.getLogger(__name__)

# Base folder in Cloudinary for all Sikapa audio assets
_CLOUDINARY_FOLDER = "sikapa"

# In-memory URL cache: avoids redundant Cloudinary API lookups for
# assets that have already been resolved during this server lifecycle.
_URL_CACHE: dict[str, str] = {}

# Flag to track whether Cloudinary SDK has been configured this session
_configured = False


def _ensure_configured() -> None:
    """Initialize the Cloudinary SDK with credentials from AISettings.

    Called lazily on first use. Raises RuntimeError if credentials
    are missing so the developer gets a clear, actionable error.
    """
    global _configured
    if _configured:
        return

    settings = get_ai_settings()
    if not all([
        settings.cloudinary_cloud_name,
        settings.cloudinary_api_key,
        settings.cloudinary_api_secret,
    ]):
        raise RuntimeError(
            "Cloudinary is not configured. "
            "Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and "
            "CLOUDINARY_API_SECRET in your .env file."
        )

    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )
    _configured = True
    logger.info("Cloudinary SDK configured for cloud: %s", settings.cloudinary_cloud_name)


def build_public_id(folder: str, name: str) -> str:
    """Build a deterministic Cloudinary public ID.

    Example: build_public_id("en_digits", "20") -> "sikapa/en_digits/20"
    """
    return f"{_CLOUDINARY_FOLDER}/{folder}/{name}"


def get_cached_url(public_id: str) -> Optional[str]:
    """Return the CDN URL from the in-memory cache, or None if not cached."""
    return _URL_CACHE.get(public_id)


def build_cdn_url(public_id: str, file_format: str = "mp3") -> str:
    """Build the Cloudinary CDN URL for a known public ID.

    This does NOT make an API call — it simply constructs the
    deterministic URL from the cloud name and public ID.
    """
    _ensure_configured()
    settings = get_ai_settings()
    url = (
        f"https://res.cloudinary.com/{settings.cloudinary_cloud_name}"
        f"/video/upload/{public_id}.{file_format}"
    )
    _URL_CACHE[public_id] = url
    return url


def upload_audio_bytes(
    audio_bytes: bytes,
    public_id: str,
    file_format: str = "mp3",
) -> str:
    """Upload raw audio bytes to Cloudinary and return the secure CDN URL.

    Uses a deterministic ``public_id`` so repeated uploads of the same
    content are idempotent (Cloudinary overwrites the existing asset).

    Args:
        audio_bytes: Raw audio data (MP3 or WAV).
        public_id: Unique identifier in Cloudinary (e.g. "sikapa/amounts/125_50").
        file_format: File extension hint for Cloudinary ("mp3" or "wav").

    Returns:
        The HTTPS CDN URL for the uploaded audio asset.
    """
    # Skip upload if we already have a cached URL for this public_id
    cached = get_cached_url(public_id)
    if cached:
        logger.debug("Cloudinary cache hit for %s", public_id)
        return cached

    _ensure_configured()

    # Cloudinary's Python SDK expects a file path or file-like object.
    # We write bytes to a temporary file to avoid in-memory issues.
    suffix = f".{file_format}"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        result = cloudinary.uploader.upload(
            tmp_path,
            resource_type="video",  # Cloudinary uses "video" for audio
            public_id=public_id,
            overwrite=True,
            invalidate=True,       # Purge CDN cache on overwrite
        )
    finally:
        # Clean up temp file regardless of upload success
        Path(tmp_path).unlink(missing_ok=True)

    url = result.get("secure_url", "")
    if not url:
        raise RuntimeError(f"Cloudinary upload failed for {public_id}: {result}")

    _URL_CACHE[public_id] = url
    logger.info("Uploaded to Cloudinary: %s -> %s", public_id, url)
    return url


def upload_local_file(file_path: Path, folder: str) -> str:
    """Upload a local audio file to Cloudinary.

    The public_id is derived from the folder and filename stem.
    Example: upload_local_file(Path("ai/assets/twi/politeness.wav"), "twi")
             -> public_id = "sikapa/twi/politeness"

    Returns:
        The HTTPS CDN URL for the uploaded audio asset.
    """
    _ensure_configured()
    public_id = build_public_id(folder, file_path.stem)

    result = cloudinary.uploader.upload(
        str(file_path),
        resource_type="video",
        public_id=public_id,
        overwrite=True,
        invalidate=True,
    )

    url = result.get("secure_url", "")
    if not url:
        raise RuntimeError(f"Cloudinary upload failed for {public_id}: {result}")

    _URL_CACHE[public_id] = url
    logger.info("Uploaded to Cloudinary: %s -> %s", public_id, url)
    return url

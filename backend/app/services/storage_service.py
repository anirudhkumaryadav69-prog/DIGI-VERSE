"""Image upload validation and storage provider abstraction.

Security guarantees:
- Validates file extension, declared Content-Type, AND actual binary magic bytes (PNG, JPEG, WebP).
- Rejects executable, SVG/HTML, empty, or oversized files.
- Generates opaque server-side UUID filenames (`<uuid32>.<ext>`); never trusts client filenames.
- Enforces strict path traversal protection (`Path.resolve()` containment check).
"""
import re
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
SAFE_FILENAME_REGEX = re.compile(r"^[a-f0-9]{32}\.(jpg|jpeg|png|webp)$")

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def detect_image_mime_from_magic_bytes(data: bytes) -> Optional[tuple[str, str]]:
    """Inspect binary file header magic bytes. Returns (mime_type, canonical_ext) or None."""
    if len(data) < 12:
        return None
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return None


def validate_and_read_image_upload(
    upload: UploadFile,
    max_bytes: Optional[int] = None,
) -> tuple[bytes, str, str]:
    """Read and validate an uploaded image file.

    Returns (raw_bytes, detected_mime_type, safe_server_filename).
    """
    limit = max_bytes or settings.MAX_IMAGE_UPLOAD_BYTES
    original_name = (upload.filename or "").strip()
    ext = Path(original_name).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported image file extension. Allowed formats: JPG, JPEG, PNG, WEBP.",
        )

    declared_type = (upload.content_type or "").lower().split(";")[0].strip()
    if declared_type and declared_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported image Content-Type. Allowed formats: image/jpeg, image/png, image/webp.",
        )

    data = upload.file.read(limit + 1)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image file is empty.",
        )
    if len(data) > limit:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image file exceeds maximum allowed size of {limit // (1024 * 1024)} MB.",
        )

    detected = detect_image_mime_from_magic_bytes(data)
    if not detected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match a valid PNG, JPEG, or WEBP image signature.",
        )

    detected_mime, canonical_ext = detected
    if declared_type and declared_type != detected_mime:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Declared Content-Type does not match actual image file signature.",
        )
    # Prevent extension / magic-byte spoofing (e.g. a PNG renamed to .jpg or vice versa)
    expected_exts_for_mime = {
        "image/png": {".png"},
        "image/jpeg": {".jpg", ".jpeg"},
        "image/webp": {".webp"},
    }
    if ext not in expected_exts_for_mime[detected_mime]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File extension does not match actual image format.",
        )

    safe_filename = f"{uuid.uuid4().hex}{canonical_ext}"
    return data, detected_mime, safe_filename


class ImageStorageProvider(ABC):
    @abstractmethod
    def save_image(self, upload: UploadFile) -> str:
        """Validate and persist an uploaded image, returning its public URL path."""

    @abstractmethod
    def delete_image(self, image_url: str) -> None:
        """Delete a managed image by its URL if it resides in managed storage."""

    @abstractmethod
    def resolve_local_path(self, filename: str) -> Path:
        """Resolve and verify a safe local path for serving an uploaded image."""


class LocalImageStorageProvider(ImageStorageProvider):
    def __init__(self, base_dir: Optional[Path] = None) -> None:
        configured = Path(settings.UPLOAD_DIR)
        self.base_dir = (
            base_dir
            if base_dir is not None
            else (configured if configured.is_absolute() else (BACKEND_ROOT / configured))
        ).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _safe_target_path(self, filename: str) -> Path:
        if not SAFE_FILENAME_REGEX.match(filename):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image filename.",
            )
        candidate = (self.base_dir / filename).resolve()
        if candidate.parent != self.base_dir:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path traversal attempt blocked.",
            )
        return candidate

    def save_image(self, upload: UploadFile) -> str:
        data, _, safe_filename = validate_and_read_image_upload(upload)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        target = self._safe_target_path(safe_filename)
        target.write_bytes(data)
        return f"/api/uploads/images/{safe_filename}"

    def delete_image(self, image_url: str) -> None:
        prefix = "/api/uploads/images/"
        if not image_url or not image_url.startswith(prefix):
            return
        filename = image_url[len(prefix) :]
        if not SAFE_FILENAME_REGEX.match(filename):
            return
        target = (self.base_dir / filename).resolve()
        if target.parent == self.base_dir and target.is_file():
            try:
                target.unlink()
            except OSError:
                pass

    def resolve_local_path(self, filename: str) -> Path:
        target = self._safe_target_path(filename)
        if not target.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image not found.",
            )
        return target


_storage_provider = LocalImageStorageProvider()


def get_image_storage() -> ImageStorageProvider:
    return _storage_provider

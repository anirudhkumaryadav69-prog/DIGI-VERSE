"""Image upload validation and storage provider abstraction.

Security guarantees:
- Validates file extension, declared Content-Type, AND actual binary magic bytes (PNG, JPEG, WebP).
- Rejects executable, SVG/HTML, empty, or oversized files.
- Generates opaque server-side UUID filenames (`<uuid32>.<ext>`); never trusts client filenames.
- Enforces strict path traversal protection (`Path.resolve()` containment check).
"""
import hashlib
import io
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Optional

import httpx
from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.services.s3_client import STREAM_CHUNK_BYTES, S3ClientError, S3ObjectNotFoundError, S3SigV4Client

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
SAFE_FILENAME_REGEX = re.compile(r"^[a-f0-9]{32}\.(jpg|jpeg|png|webp)$")
IMAGE_MEDIA_TYPE_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}

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


@dataclass
class ImageStreamHandle:
    chunk_iterator: Iterator[bytes]
    close_callback: Callable[[], None]
    content_type: str
    size_bytes: Optional[int] = None

    def iter_chunks(self) -> Iterator[bytes]:
        try:
            for chunk in self.chunk_iterator:
                yield chunk
        finally:
            self.close()

    def close(self) -> None:
        self.close_callback()


class ImageStorageProvider(ABC):
    backend_name: str = "base"

    @abstractmethod
    def save_image(self, upload: UploadFile) -> str:
        """Validate and persist an uploaded image, returning its public URL path."""

    @abstractmethod
    def delete_image(self, image_url: str) -> None:
        """Delete a managed image by its URL if it resides in managed storage."""

    @abstractmethod
    def resolve_local_path(self, filename: str) -> Path:
        """Resolve and verify a safe local path for serving a locally stored image."""

    @abstractmethod
    def open_image(self, filename: str) -> ImageStreamHandle:
        """Open a validated public image stream for serving via API."""


def _validate_image_filename(filename: str) -> str:
    if not SAFE_FILENAME_REGEX.match(filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image filename.",
        )
    return filename


class LocalImageStorageProvider(ImageStorageProvider):
    backend_name = "local"

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        configured = Path(settings.UPLOAD_DIR)
        self.base_dir = (
            base_dir
            if base_dir is not None
            else (configured if configured.is_absolute() else (BACKEND_ROOT / configured))
        ).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _safe_target_path(self, filename: str) -> Path:
        _validate_image_filename(filename)
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

    def open_image(self, filename: str) -> ImageStreamHandle:
        target = self.resolve_local_path(filename)
        ext = target.suffix.lower()
        stat = target.stat()
        fh = open(target, "rb")

        def _chunks() -> Iterator[bytes]:
            while True:
                chunk = fh.read(STREAM_CHUNK_BYTES)
                if not chunk:
                    break
                yield chunk

        return ImageStreamHandle(
            chunk_iterator=_chunks(),
            close_callback=fh.close,
            content_type=IMAGE_MEDIA_TYPE_MAP.get(ext, "application/octet-stream"),
            size_bytes=stat.st_size,
        )


class S3ImageStorageProvider(ImageStorageProvider):
    """Cloudflare R2 / S3-compatible public image storage streamed through `/api/uploads/images/{filename}`."""

    backend_name = "s3"

    def __init__(
        self,
        *,
        bucket: Optional[str] = None,
        region: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        use_path_style: Optional[bool] = None,
        prefix: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        resolved = settings.resolve_image_s3_settings()
        self.bucket = (bucket if bucket is not None else str(resolved["bucket"])).strip()
        self.region = (region if region is not None else str(resolved["region"])).strip() or "auto"
        self.endpoint_url = (
            endpoint_url if endpoint_url is not None else str(resolved["endpoint_url"])
        ).strip().rstrip("/")
        self.access_key = (access_key if access_key is not None else str(resolved["access_key"])).strip()
        self.secret_key = (secret_key if secret_key is not None else str(resolved["secret_key"])).strip()
        self.use_path_style = bool(resolved["use_path_style"] if use_path_style is None else use_path_style)
        self.timeout_seconds = timeout_seconds or int(resolved["timeout_seconds"])
        self.prefix = (prefix if prefix is not None else str(resolved["prefix"])).strip("/ ") or "public-images"

        private_bucket = (settings.ASSET_STORAGE_BUCKET or "").strip()
        if self.bucket and private_bucket and self.bucket == private_bucket:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Public image storage bucket must be separate from private asset bucket.",
            )

        try:
            self._s3 = S3SigV4Client(
                bucket=self.bucket,
                region=self.region,
                endpoint_url=self.endpoint_url,
                access_key=self.access_key,
                secret_key=self.secret_key,
                use_path_style=self.use_path_style,
                timeout_seconds=self.timeout_seconds,
                require_https=settings.is_production,
                transport=transport,
            )
        except S3ClientError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Public image storage (R2/S3) is not completely configured.",
            ) from exc

    def _object_key(self, safe_filename: str) -> str:
        clean = _validate_image_filename(safe_filename)
        return f"{self.prefix}/{clean}" if self.prefix else clean

    def save_image(self, upload: UploadFile) -> str:
        data, detected_mime, safe_filename = validate_and_read_image_upload(upload)
        sha256_hex = hashlib.sha256(data).hexdigest()
        object_key = self._object_key(safe_filename)
        try:
            self._s3.put_stream(
                key=object_key,
                file_obj=io.BytesIO(data),
                content_type=detected_mime,
                size_bytes=len(data),
                sha256_hex=sha256_hex,
                extra_headers={"Cache-Control": "public, max-age=86400"},
            )
        except S3ClientError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Public image storage upload failed.",
            ) from exc
        return f"/api/uploads/images/{safe_filename}"

    def delete_image(self, image_url: str) -> None:
        prefix = "/api/uploads/images/"
        if not image_url or not image_url.startswith(prefix):
            return
        filename = image_url[len(prefix) :]
        if not SAFE_FILENAME_REGEX.match(filename):
            return
        self._s3.delete_object(key=self._object_key(filename))

    def resolve_local_path(self, filename: str) -> Path:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Images are served from remote object storage, not local disk.",
        )

    def open_image(self, filename: str) -> ImageStreamHandle:
        clean = _validate_image_filename(filename)
        ext = Path(clean).suffix.lower()
        try:
            res = self._s3.open_stream(key=self._object_key(clean), chunk_size=STREAM_CHUNK_BYTES)
        except S3ObjectNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image not found.",
            ) from exc
        except S3ClientError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to retrieve public image from object storage.",
            ) from exc
        return ImageStreamHandle(
            chunk_iterator=res.chunk_iterator,
            close_callback=res.close_callback,
            content_type=res.content_type or IMAGE_MEDIA_TYPE_MAP.get(ext, "application/octet-stream"),
            size_bytes=res.size_bytes,
        )


class DisabledImageStorageProvider(ImageStorageProvider):
    """Fail-closed public image provider when R2/S3 is not configured in production."""

    backend_name = "disabled"

    def save_image(self, upload: UploadFile) -> str:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Public image storage (R2/S3) is not configured in this environment.",
        )

    def delete_image(self, image_url: str) -> None:
        return None

    def resolve_local_path(self, filename: str) -> Path:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Public image storage (R2/S3) is not configured in this environment.",
        )

    def open_image(self, filename: str) -> ImageStreamHandle:
        _validate_image_filename(filename)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Public image storage (R2/S3) is not configured in this environment.",
        )


def get_image_storage(backend_override: Optional[str] = None) -> ImageStorageProvider:
    """Resolve active public image storage backend; never falls back to local disk in production."""
    backend = (backend_override or settings.IMAGE_STORAGE_BACKEND or "local").strip().lower()
    if backend == "disabled":
        return DisabledImageStorageProvider()
    if backend == "local":
        if settings.is_production:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Local public image storage cannot be used in production.",
            )
        return LocalImageStorageProvider()
    if backend == "s3":
        return S3ImageStorageProvider()
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Unsupported public image storage backend configured.",
    )

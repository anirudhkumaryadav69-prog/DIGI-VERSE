"""Private digital asset upload validation and storage provider abstraction.

Security guarantees:
- Validates file extensions, declared MIME types, AND actual binary magic bytes / signatures.
- Explicitly blocks executables, HTML/SVG/active scripts, empty files, and oversized uploads.
- Rejects path-traversal filenames (`..`, slashes, NUL bytes) and never uses client filenames
  as filesystem paths or object keys.
- Stores assets in private storage strictly outside public frontend and static image directories.
- Supports local private filesystem storage (dev/staging) and S3-compatible private bucket storage
  (production) using AWS Signature Version 4 over `httpx` streaming without generating public URLs.
"""
import hashlib
import hmac
import json
import os
import re
import tempfile
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Callable, Iterator, Optional
from urllib.parse import quote, urlparse

import httpx
from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.services.s3_client import S3ClientError, S3ObjectNotFoundError, S3SigV4Client

BACKEND_ROOT = Path(__file__).resolve().parents[2]
STREAM_READ_CHUNK_BYTES = 64 * 1024

STORAGE_KEY_REGEX = re.compile(r"^[a-z0-9][a-z0-9_-]*(?:/[a-zA-Z0-9._-]+)+$")

FORBIDDEN_MIME_TYPES = {
    "text/html",
    "application/xhtml+xml",
    "image/svg+xml",
    "application/javascript",
    "text/javascript",
    "application/x-javascript",
    "application/x-msdownload",
    "application/x-dosexec",
    "application/x-executable",
    "application/x-sh",
    "application/x-shellscript",
    "application/x-php",
    "text/x-php",
}

EXECUTABLE_MAGIC_PREFIXES = (
    b"MZ",
    b"\x7fELF",
    b"\xfe\xed\xfa\xce",
    b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf",
    b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe",
)

DANGEROUS_TEXT_MARKERS = (
    b"<!doctype",
    b"<html",
    b"<script",
    b"<svg",
    b"<?php",
)


@dataclass(frozen=True)
class AssetFormatRule:
    canonical_ext: str
    canonical_mime: str
    allowed_declared_mimes: frozenset[str]


ALLOWED_ASSET_FORMATS: dict[str, AssetFormatRule] = {
    ".zip": AssetFormatRule(
        canonical_ext=".zip",
        canonical_mime="application/zip",
        allowed_declared_mimes=frozenset(
            {"application/zip", "application/x-zip-compressed", "multipart/x-zip", "application/octet-stream"}
        ),
    ),
    ".fig": AssetFormatRule(
        canonical_ext=".fig",
        canonical_mime="application/octet-stream",
        allowed_declared_mimes=frozenset(
            {"application/octet-stream", "application/zip", "application/x-figma"}
        ),
    ),
    ".pdf": AssetFormatRule(
        canonical_ext=".pdf",
        canonical_mime="application/pdf",
        allowed_declared_mimes=frozenset({"application/pdf", "application/octet-stream"}),
    ),
    ".epub": AssetFormatRule(
        canonical_ext=".epub",
        canonical_mime="application/epub+zip",
        allowed_declared_mimes=frozenset(
            {"application/epub+zip", "application/zip", "application/octet-stream"}
        ),
    ),
    ".7z": AssetFormatRule(
        canonical_ext=".7z",
        canonical_mime="application/x-7z-compressed",
        allowed_declared_mimes=frozenset(
            {"application/x-7z-compressed", "application/octet-stream"}
        ),
    ),
    ".gz": AssetFormatRule(
        canonical_ext=".gz",
        canonical_mime="application/gzip",
        allowed_declared_mimes=frozenset(
            {"application/gzip", "application/x-gzip", "application/octet-stream"}
        ),
    ),
    ".png": AssetFormatRule(
        canonical_ext=".png",
        canonical_mime="image/png",
        allowed_declared_mimes=frozenset({"image/png"}),
    ),
    ".jpg": AssetFormatRule(
        canonical_ext=".jpg",
        canonical_mime="image/jpeg",
        allowed_declared_mimes=frozenset({"image/jpeg"}),
    ),
    ".jpeg": AssetFormatRule(
        canonical_ext=".jpg",
        canonical_mime="image/jpeg",
        allowed_declared_mimes=frozenset({"image/jpeg"}),
    ),
    ".webp": AssetFormatRule(
        canonical_ext=".webp",
        canonical_mime="image/webp",
        allowed_declared_mimes=frozenset({"image/webp"}),
    ),
    ".mp3": AssetFormatRule(
        canonical_ext=".mp3",
        canonical_mime="audio/mpeg",
        allowed_declared_mimes=frozenset({"audio/mpeg", "audio/mp3", "application/octet-stream"}),
    ),
    ".wav": AssetFormatRule(
        canonical_ext=".wav",
        canonical_mime="audio/wav",
        allowed_declared_mimes=frozenset(
            {"audio/wav", "audio/x-wav", "audio/wave", "application/octet-stream"}
        ),
    ),
    ".mp4": AssetFormatRule(
        canonical_ext=".mp4",
        canonical_mime="video/mp4",
        allowed_declared_mimes=frozenset({"video/mp4", "application/octet-stream"}),
    ),
    ".woff2": AssetFormatRule(
        canonical_ext=".woff2",
        canonical_mime="font/woff2",
        allowed_declared_mimes=frozenset({"font/woff2", "application/font-woff2", "application/octet-stream"}),
    ),
    ".ttf": AssetFormatRule(
        canonical_ext=".ttf",
        canonical_mime="font/ttf",
        allowed_declared_mimes=frozenset({"font/ttf", "application/x-font-ttf", "application/octet-stream"}),
    ),
    ".otf": AssetFormatRule(
        canonical_ext=".otf",
        canonical_mime="font/otf",
        allowed_declared_mimes=frozenset(
            {"font/otf", "application/vnd.ms-opentype", "application/octet-stream"}
        ),
    ),
    ".json": AssetFormatRule(
        canonical_ext=".json",
        canonical_mime="application/json",
        allowed_declared_mimes=frozenset(
            {"application/json", "text/json", "text/plain", "application/octet-stream"}
        ),
    ),
    ".txt": AssetFormatRule(
        canonical_ext=".txt",
        canonical_mime="text/plain",
        allowed_declared_mimes=frozenset({"text/plain", "application/octet-stream"}),
    ),
    ".md": AssetFormatRule(
        canonical_ext=".md",
        canonical_mime="text/markdown",
        allowed_declared_mimes=frozenset({"text/markdown", "text/x-markdown", "text/plain", "application/octet-stream"}),
    ),
    ".csv": AssetFormatRule(
        canonical_ext=".csv",
        canonical_mime="text/csv",
        allowed_declared_mimes=frozenset(
            {"text/csv", "application/csv", "text/plain", "application/octet-stream"}
        ),
    ),
}

ALLOWED_ASSET_EXTENSIONS_DISPLAY = ", ".join(sorted(ALLOWED_ASSET_FORMATS.keys()))


class AssetNotFoundError(Exception):
    """Raised when a referenced asset does not exist in private storage."""


class AssetStorageError(Exception):
    """Raised when private storage operations fail safely without leaking internals."""


@dataclass(frozen=True)
class StoredAssetMetadata:
    storage_key: str
    storage_backend: str
    size_bytes: int
    content_type: str
    sha256: Optional[str] = None
    etag: Optional[str] = None


@dataclass
class ValidatedSpooledAsset:
    spool: tempfile.SpooledTemporaryFile[bytes]
    storage_key: str
    display_filename: str
    canonical_ext: str
    content_type: str
    size_bytes: int
    sha256: str

    def close(self) -> None:
        try:
            self.spool.close()
        except Exception:
            pass


class AssetStreamHandle:
    """Streaming handle wrapping chunk iteration and deterministic resource cleanup."""

    def __init__(
        self,
        chunk_iterator: Iterator[bytes],
        close_callback: Callable[[], None],
        size_bytes: Optional[int] = None,
        content_type: Optional[str] = None,
    ) -> None:
        self._iterator = chunk_iterator
        self._close_callback = close_callback
        self.size_bytes = size_bytes
        self.content_type = content_type
        self._closed = False

    def iter_chunks(self) -> Iterator[bytes]:
        try:
            for chunk in self._iterator:
                if chunk:
                    yield chunk
        finally:
            self.close()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            try:
                self._close_callback()
            except Exception:
                pass


def sanitize_display_filename(raw_filename: Optional[str], fallback_ext: str = ".bin") -> str:
    """Produce a safe basename for display and Content-Disposition without trusting raw input."""
    raw = (raw_filename or "").replace("\x00", "").strip()
    base = raw.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    stem = Path(base).stem
    clean_stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", stem).strip(" ._")
    clean_stem = re.sub(r"\s{2,}", " ", clean_stem)
    if not clean_stem:
        clean_stem = "digital-asset"
    ext = fallback_ext if fallback_ext.startswith(".") else f".{fallback_ext}"
    max_stem_len = max(16, 180 - len(ext))
    return f"{clean_stem[:max_stem_len]}{ext}"


def validate_unsafe_upload_filename(raw_filename: Optional[str]) -> str:
    """Reject traversal, directory separators, NUL bytes, or empty upload filenames."""
    name = (raw_filename or "").strip()
    if (
        not name
        or "\x00" in name
        or ".." in name
        or "/" in name
        or "\\" in name
        or re.search(r"(?i)%2e%2e|%2f|%5c", name)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or unsafe asset filename.",
        )
    return name


def build_download_content_disposition(filename: Optional[str], fallback_name: str = "digiverse-asset.bin") -> str:
    """Construct a safe ASCII Content-Disposition header immune to CRLF/header injection."""
    candidate = (filename or "").replace("\r", "").replace("\n", "").replace("\x00", "").strip()
    candidate = candidate.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    safe_ascii = re.sub(r'[^A-Za-z0-9._ -]+', "_", candidate).strip(" .")
    if not safe_ascii:
        safe_ascii = fallback_name
    safe_ascii = safe_ascii[:180]
    return f'attachment; filename="{safe_ascii}"'


def validate_storage_key(storage_key: str) -> str:
    cleaned = (storage_key or "").strip()
    if (
        not cleaned
        or len(cleaned) > 512
        or cleaned.startswith("/")
        or "\\" in cleaned
        or ".." in cleaned
        or "\x00" in cleaned
        or re.search(r"(?i)%2e%2e", cleaned)
        or not STORAGE_KEY_REGEX.match(cleaned)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or unsafe asset storage key.",
        )
    return cleaned


def _has_dangerous_header(header: bytes) -> bool:
    for sig in EXECUTABLE_MAGIC_PREFIXES:
        if header.startswith(sig):
            return True
    lowered = header[:512].lstrip().lower()
    if lowered.startswith(b"#!") or any(marker in lowered for marker in DANGEROUS_TEXT_MARKERS):
        return True
    return False


def _verify_magic_signature(ext: str, header: bytes, spool: tempfile.SpooledTemporaryFile[bytes], size_bytes: int) -> None:
    if _has_dangerous_header(header):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file matches a forbidden executable or active script signature.",
        )

    if ext == ".zip":
        if not (header.startswith(b"PK\x03\x04") or header.startswith(b"PK\x05\x06")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content does not match a valid ZIP archive signature.",
            )
    elif ext == ".fig":
        if not (header.startswith(b"PK\x03\x04") or header.startswith(b"fig-kiwi")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content does not match a valid Figma design file signature.",
            )
    elif ext == ".epub":
        if not header.startswith(b"PK\x03\x04") or b"application/epub+zip" not in header[:256]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content does not match a valid EPUB signature.",
            )
    elif ext == ".pdf":
        if not header.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content does not match a valid PDF signature.",
            )
    elif ext == ".7z":
        if not header.startswith(b"7z\xbc\xaf\x27\x1c"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content does not match a valid 7z archive signature.",
            )
    elif ext == ".gz":
        if not header.startswith(b"\x1f\x8b\x08"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content does not match a valid GZIP signature.",
            )
    elif ext == ".png":
        if not header.startswith(b"\x89PNG\r\n\x1a\n"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content does not match a valid PNG image signature.",
            )
    elif ext in {".jpg", ".jpeg"}:
        if not header.startswith(b"\xff\xd8\xff"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content does not match a valid JPEG image signature.",
            )
    elif ext == ".webp":
        if len(header) < 12 or header[:4] != b"RIFF" or header[8:12] != b"WEBP":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content does not match a valid WEBP image signature.",
            )
    elif ext == ".mp3":
        is_id3 = header.startswith(b"ID3")
        is_mpeg_frame = len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0
        if not (is_id3 or is_mpeg_frame):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content does not match a valid MP3 audio signature.",
            )
    elif ext == ".wav":
        if len(header) < 12 or header[:4] != b"RIFF" or header[8:12] != b"WAVE":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content does not match a valid WAV audio signature.",
            )
    elif ext == ".mp4":
        if len(header) < 8 or header[4:8] != b"ftyp":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content does not match a valid MP4 video signature.",
            )
    elif ext == ".woff2":
        if not header.startswith(b"wOF2"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content does not match a valid WOFF2 font signature.",
            )
    elif ext == ".ttf":
        if not (header.startswith(b"\x00\x01\x00\x00") or header.startswith(b"true")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content does not match a valid TTF font signature.",
            )
    elif ext == ".otf":
        if not header.startswith(b"OTTO"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content does not match a valid OTF font signature.",
            )
    elif ext in {".json", ".txt", ".md", ".csv"}:
        if size_bytes > 20 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Text/JSON digital files cannot exceed 20 MB.",
            )
        spool.seek(0)
        raw_text_bytes = spool.read()
        if b"\x00" in raw_text_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Binary NUL bytes are not valid in text or JSON files.",
            )
        try:
            decoded = raw_text_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is not valid UTF-8 encoded text.",
            ) from exc
        if any(m.decode("ascii") in decoded[:2048].lower() for m in DANGEROUS_TEXT_MARKERS):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="HTML or embedded script content is not allowed in digital assets.",
            )
        if ext == ".json":
            try:
                json.loads(decoded)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Uploaded .json asset does not contain valid JSON.",
                ) from exc


def validate_and_spool_asset_upload(
    upload: UploadFile,
    product_id: uuid.UUID,
    max_bytes: Optional[int] = None,
) -> ValidatedSpooledAsset:
    """Validate uploaded digital product asset and stream into bounded temporary spool."""
    limit = max_bytes or settings.MAX_ASSET_UPLOAD_BYTES
    raw_filename = validate_unsafe_upload_filename(upload.filename)
    ext = Path(raw_filename).suffix.lower()
    rule = ALLOWED_ASSET_FORMATS.get(ext)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported digital asset extension '{ext or 'none'}'. Allowed: {ALLOWED_ASSET_EXTENSIONS_DISPLAY}.",
        )

    declared_type = (upload.content_type or "").lower().split(";")[0].strip()
    if declared_type in FORBIDDEN_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Forbidden active or script Content-Type rejected.",
        )
    if declared_type and declared_type not in rule.allowed_declared_mimes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Declared Content-Type '{declared_type}' does not match '{ext}' asset type.",
        )

    spool = tempfile.SpooledTemporaryFile(max_size=2 * 1024 * 1024, mode="w+b")
    hasher = hashlib.sha256()
    header_buf = bytearray()
    size_bytes = 0

    try:
        while True:
            chunk = upload.file.read(STREAM_READ_CHUNK_BYTES)
            if not chunk:
                break
            size_bytes += len(chunk)
            if size_bytes > limit:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Digital asset exceeds maximum allowed size of {max(1, limit // (1024 * 1024))} MB.",
                )
            spool.write(chunk)
            hasher.update(chunk)
            if len(header_buf) < 4096:
                needed = 4096 - len(header_buf)
                header_buf.extend(chunk[:needed])

        if size_bytes == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded digital asset file is empty.",
            )

        _verify_magic_signature(ext=ext, header=bytes(header_buf), spool=spool, size_bytes=size_bytes)
        spool.seek(0)

        storage_key = f"products/{product_id}/{uuid.uuid4().hex}{rule.canonical_ext}"
        display_filename = sanitize_display_filename(raw_filename, fallback_ext=rule.canonical_ext)
        return ValidatedSpooledAsset(
            spool=spool,
            storage_key=storage_key,
            display_filename=display_filename,
            canonical_ext=rule.canonical_ext,
            content_type=rule.canonical_mime,
            size_bytes=size_bytes,
            sha256=hasher.hexdigest(),
        )
    except Exception:
        spool.close()
        raise


class PrivateAssetStorageProvider(ABC):
    backend_name: str

    @abstractmethod
    def save(
        self,
        file_obj: BinaryIO,
        storage_key: str,
        content_type: str,
        size_bytes: int,
        sha256_hex: Optional[str] = None,
    ) -> StoredAssetMetadata:
        """Persist binary asset privately without exposing public URLs or paths."""

    @abstractmethod
    def open(
        self,
        storage_key: str,
        chunk_size: int = STREAM_READ_CHUNK_BYTES,
    ) -> AssetStreamHandle:
        """Open a private binary stream handle for authorized delivery."""

    @abstractmethod
    def delete(self, storage_key: str) -> None:
        """Delete a stored private asset if present."""

    @abstractmethod
    def exists(self, storage_key: str) -> bool:
        """Return True if the private asset currently exists in storage."""

    @abstractmethod
    def get_metadata(self, storage_key: str) -> Optional[StoredAssetMetadata]:
        """Return stored size/type metadata for an existing object or None."""


class LocalPrivateAssetStorageProvider(PrivateAssetStorageProvider):
    backend_name = "local"

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        configured = Path(settings.ASSET_STORAGE_LOCAL_ROOT)
        resolved_base = (
            base_dir
            if base_dir is not None
            else (configured if configured.is_absolute() else (BACKEND_ROOT / configured))
        ).resolve()
        self.base_dir = resolved_base
        self.tmp_dir = (self.base_dir / ".tmp").resolve()

    def _safe_target_path(self, storage_key: str) -> Path:
        clean_key = validate_storage_key(storage_key)
        candidate = (self.base_dir / clean_key).resolve()
        if not candidate.is_relative_to(self.base_dir) or candidate.is_relative_to(self.tmp_dir):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsafe asset storage path blocked.",
            )
        return candidate

    def save(
        self,
        file_obj: BinaryIO,
        storage_key: str,
        content_type: str,
        size_bytes: int,
        sha256_hex: Optional[str] = None,
    ) -> StoredAssetMetadata:
        target = self._safe_target_path(storage_key)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        target.parent.mkdir(parents=True, exist_ok=True)

        tmp_path = self.tmp_dir / f".upload-{uuid.uuid4().hex}.part"
        written = 0
        hasher = hashlib.sha256()
        try:
            file_obj.seek(0)
            with open(tmp_path, "wb") as out:
                while True:
                    chunk = file_obj.read(STREAM_READ_CHUNK_BYTES)
                    if not chunk:
                        break
                    out.write(chunk)
                    hasher.update(chunk)
                    written += len(chunk)
            os.replace(tmp_path, target)
        except OSError as exc:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
            raise AssetStorageError("Unable to persist digital asset to private storage.") from exc

        return StoredAssetMetadata(
            storage_key=storage_key,
            storage_backend=self.backend_name,
            size_bytes=written,
            content_type=content_type,
            sha256=sha256_hex or hasher.hexdigest(),
        )

    def open(
        self,
        storage_key: str,
        chunk_size: int = STREAM_READ_CHUNK_BYTES,
    ) -> AssetStreamHandle:
        target = self._safe_target_path(storage_key)
        if not target.is_file():
            raise AssetNotFoundError("Digital asset file not found in private storage.")
        try:
            stat = target.stat()
            fh = open(target, "rb")
        except FileNotFoundError as exc:
            raise AssetNotFoundError("Digital asset file not found in private storage.") from exc
        except OSError as exc:
            raise AssetStorageError("Unable to open digital asset stream.") from exc

        def _chunks() -> Iterator[bytes]:
            while True:
                data = fh.read(chunk_size)
                if not data:
                    break
                yield data

        return AssetStreamHandle(
            chunk_iterator=_chunks(),
            close_callback=fh.close,
            size_bytes=stat.st_size,
        )

    def delete(self, storage_key: str) -> None:
        try:
            target = self._safe_target_path(storage_key)
        except HTTPException:
            return
        if target.is_file():
            try:
                target.unlink()
            except OSError:
                pass

    def exists(self, storage_key: str) -> bool:
        try:
            target = self._safe_target_path(storage_key)
        except HTTPException:
            return False
        return target.is_file()

    def get_metadata(self, storage_key: str) -> Optional[StoredAssetMetadata]:
        try:
            target = self._safe_target_path(storage_key)
        except HTTPException:
            return None
        if not target.is_file():
            return None
        return StoredAssetMetadata(
            storage_key=storage_key,
            storage_backend=self.backend_name,
            size_bytes=target.stat().st_size,
            content_type="application/octet-stream",
        )


def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


class S3PrivateAssetStorageProvider(PrivateAssetStorageProvider):
    """Private-bucket S3-compatible object storage adapter using AWS SigV4 + httpx."""

    backend_name = "s3"

    def __init__(
        self,
        bucket: Optional[str] = None,
        region: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        use_path_style: Optional[bool] = None,
        timeout_seconds: Optional[int] = None,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self.bucket = (bucket if bucket is not None else (settings.ASSET_STORAGE_BUCKET or "")).strip()
        self.region = (region if region is not None else (settings.ASSET_STORAGE_REGION or "us-east-1")).strip() or "us-east-1"
        self.endpoint_url = (
            endpoint_url if endpoint_url is not None else (settings.ASSET_STORAGE_ENDPOINT_URL or "")
        ).strip().rstrip("/")
        self.access_key = (access_key if access_key is not None else (settings.ASSET_STORAGE_ACCESS_KEY or "")).strip()
        self.secret_key = (secret_key if secret_key is not None else (settings.ASSET_STORAGE_SECRET_KEY or "")).strip()
        self.use_path_style = settings.ASSET_STORAGE_USE_PATH_STYLE if use_path_style is None else use_path_style
        self.timeout_seconds = timeout_seconds or settings.ASSET_STORAGE_TIMEOUT_SECONDS
        self._transport = transport

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
                transport=self._transport,
            )
        except S3ClientError as exc:
            raise AssetStorageError("S3 private asset storage is not completely configured.") from exc

    def _signed_headers(
        self,
        method: str,
        storage_key: str,
        payload_sha256: str = "UNSIGNED-PAYLOAD",
        extra_headers: Optional[dict[str, str]] = None,
    ) -> tuple[str, dict[str, str]]:
        clean_key = validate_storage_key(storage_key)
        return self._s3.signed_headers(
            method=method,
            key=clean_key,
            payload_sha256=payload_sha256,
            extra_headers=extra_headers,
        )

    def save(
        self,
        file_obj: BinaryIO,
        storage_key: str,
        content_type: str,
        size_bytes: int,
        sha256_hex: Optional[str] = None,
    ) -> StoredAssetMetadata:
        clean_key = validate_storage_key(storage_key)
        try:
            res = self._s3.put_stream(
                key=clean_key,
                file_obj=file_obj,
                content_type=content_type,
                size_bytes=size_bytes,
                sha256_hex=sha256_hex,
            )
            return StoredAssetMetadata(
                storage_key=clean_key,
                storage_backend=self.backend_name,
                size_bytes=res.size_bytes,
                content_type=res.content_type,
                sha256=res.sha256,
                etag=res.etag,
            )
        except S3ClientError as exc:
            raise AssetStorageError("Private object storage upload failed.") from exc

    def open(
        self,
        storage_key: str,
        chunk_size: int = STREAM_READ_CHUNK_BYTES,
    ) -> AssetStreamHandle:
        clean_key = validate_storage_key(storage_key)
        try:
            res = self._s3.open_stream(key=clean_key, chunk_size=chunk_size)
            return AssetStreamHandle(
                chunk_iterator=res.chunk_iterator,
                close_callback=res.close_callback,
                size_bytes=res.size_bytes,
                content_type=res.content_type,
            )
        except S3ObjectNotFoundError as exc:
            raise AssetNotFoundError("Digital asset file not found in private storage.") from exc
        except S3ClientError as exc:
            raise AssetStorageError("Unable to stream asset from private object storage.") from exc

    def delete(self, storage_key: str) -> None:
        try:
            clean_key = validate_storage_key(storage_key)
            self._s3.delete_object(key=clean_key)
        except Exception:
            pass

    def exists(self, storage_key: str) -> bool:
        try:
            return self.get_metadata(storage_key) is not None
        except AssetStorageError:
            return False

    def get_metadata(self, storage_key: str) -> Optional[StoredAssetMetadata]:
        clean_key = validate_storage_key(storage_key)
        try:
            res = self._s3.head_object(key=clean_key)
            if res is None:
                return None
            return StoredAssetMetadata(
                storage_key=clean_key,
                storage_backend=self.backend_name,
                size_bytes=res.size_bytes,
                content_type=res.content_type,
                etag=res.etag,
            )
        except S3ClientError as exc:
            raise AssetStorageError("Private object storage metadata lookup failed.") from exc


class DisabledPrivateAssetStorageProvider(PrivateAssetStorageProvider):
    """Fail-closed private asset provider when S3/R2 storage is disabled or unavailable."""

    backend_name = "disabled"

    def save(
        self,
        file_obj: BinaryIO,
        storage_key: str,
        content_type: str,
        size_bytes: int,
        sha256_hex: Optional[str] = None,
    ) -> StoredAssetMetadata:
        raise AssetStorageError("Private digital asset storage (R2/S3) is not configured in this environment.")

    def open(self, storage_key: str, chunk_size: int = STREAM_READ_CHUNK_BYTES) -> AssetStreamHandle:
        raise AssetStorageError("Private digital asset storage (R2/S3) is not configured in this environment.")

    def delete(self, storage_key: str) -> None:
        return None

    def exists(self, storage_key: str) -> bool:
        return False

    def get_metadata(self, storage_key: str) -> Optional[StoredAssetMetadata]:
        return None


def get_asset_storage(backend_override: Optional[str] = None) -> PrivateAssetStorageProvider:
    """Resolve the active private digital asset storage provider from configuration.

    Never falls back silently to local disk in production.
    """
    backend = (backend_override or settings.ASSET_STORAGE_BACKEND or "local").strip().lower()
    if backend == "disabled":
        return DisabledPrivateAssetStorageProvider()
    if backend == "local":
        if settings.is_production:
            raise AssetStorageError("Local private asset storage cannot be used in production.")
        return LocalPrivateAssetStorageProvider()
    if backend == "s3":
        return S3PrivateAssetStorageProvider()
    raise AssetStorageError(f"Unsupported private asset storage backend configured: '{backend}'.")

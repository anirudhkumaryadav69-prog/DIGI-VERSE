"""Shared AWS SigV4 HTTP client for S3-compatible object storage (Cloudflare R2, AWS S3)."""
from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import BinaryIO, Callable, Iterator, Optional
from urllib.parse import quote, urlparse

import httpx

STREAM_CHUNK_BYTES = 64 * 1024
UNSAFE_S3_KEY_RE = re.compile(r"(?:^/|\\|\.\.|[\x00-\x1f\x7f])")
AWS_REGION_RE = re.compile(r"^[a-z]{2}(?:-[a-z]+)+-[0-9]+$")


class S3ClientError(RuntimeError):
    """Raised when an S3-compatible object storage operation fails or is misconfigured."""


class S3ObjectNotFoundError(S3ClientError):
    """Raised when an S3-compatible object does not exist."""


@dataclass(frozen=True)
class S3PutResult:
    size_bytes: int
    content_type: str
    sha256: Optional[str] = None
    etag: Optional[str] = None


@dataclass
class S3StreamResult:
    chunk_iterator: Iterator[bytes]
    close_callback: Callable[[], None]
    size_bytes: Optional[int] = None
    content_type: Optional[str] = None

    def iter_chunks(self) -> Iterator[bytes]:
        try:
            for chunk in self.chunk_iterator:
                yield chunk
        finally:
            self.close()

    def close(self) -> None:
        self.close_callback()


def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def validate_s3_object_key(key: str) -> str:
    cleaned = (key or "").strip()
    if not cleaned or UNSAFE_S3_KEY_RE.search(cleaned):
        raise S3ClientError("Invalid or unsafe object storage key.")
    return cleaned


class S3SigV4Client:
    """Minimal S3-compatible object storage client using AWS SigV4 and httpx."""

    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        endpoint_url: Optional[str],
        access_key: str,
        secret_key: str,
        use_path_style: bool = True,
        timeout_seconds: int = 60,
        require_https: bool = False,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self.bucket = (bucket or "").strip()
        self.region = (region or "auto").strip() or "auto"
        self.endpoint_url = (endpoint_url or "").strip().rstrip("/")
        self.access_key = (access_key or "").strip()
        self.secret_key = (secret_key or "").strip()
        self.use_path_style = use_path_style
        self.timeout_seconds = timeout_seconds
        self._transport = transport

        if not self.bucket or not self.access_key or not self.secret_key:
            raise S3ClientError("S3-compatible object storage credentials are not completely configured.")

        if self.endpoint_url:
            parsed = urlparse(self.endpoint_url)
            ep_host = (parsed.hostname or "").strip()
            if (
                any(ch.isspace() for ch in self.endpoint_url)
                or not parsed.netloc
                or not ep_host
                or parsed.scheme not in {"http", "https"}
            ):
                raise S3ClientError("S3-compatible object storage endpoint URL is invalid.")
            if require_https and parsed.scheme != "https":
                raise S3ClientError("S3-compatible object storage endpoint URL must use HTTPS.")
        else:
            if self.region.lower() == "auto" or not AWS_REGION_RE.match(self.region.lower()):
                raise S3ClientError(
                    "S3-compatible endpoint URL is required when using Cloudflare R2 ('auto') or a non-AWS region."
                )

    def _object_url_and_path(self, key: str) -> tuple[str, str, str]:
        clean_key = validate_s3_object_key(key)
        encoded_key = quote(clean_key, safe="/-_.~")
        if self.endpoint_url:
            parsed = urlparse(self.endpoint_url)
            base_path = parsed.path.rstrip("/")
            if self.use_path_style:
                host = parsed.netloc
                canonical_uri = f"{base_path}/{quote(self.bucket, safe='-_.~')}/{encoded_key}"
                url = f"{parsed.scheme}://{host}{canonical_uri}"
            else:
                host = f"{self.bucket}.{parsed.netloc}"
                canonical_uri = f"{base_path}/{encoded_key}"
                url = f"{parsed.scheme}://{host}{canonical_uri}"
        else:
            host = f"{self.bucket}.s3.{self.region}.amazonaws.com"
            canonical_uri = f"/{encoded_key}"
            url = f"https://{host}{canonical_uri}"
        return url, host, canonical_uri

    def signed_headers(
        self,
        *,
        method: str,
        key: str,
        payload_sha256: str = "UNSIGNED-PAYLOAD",
        extra_headers: Optional[dict[str, str]] = None,
    ) -> tuple[str, dict[str, str]]:
        url, host, canonical_uri = self._object_url_and_path(key)
        now = datetime.now(timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")

        headers_to_sign: dict[str, str] = {
            "host": host,
            "x-amz-content-sha256": payload_sha256,
            "x-amz-date": amz_date,
        }
        outgoing_headers: dict[str, str] = {
            "Host": host,
            "x-amz-content-sha256": payload_sha256,
            "x-amz-date": amz_date,
        }
        if extra_headers:
            for k, v in extra_headers.items():
                headers_to_sign[k.lower()] = v.strip()
                outgoing_headers[k] = v.strip()

        sorted_keys = sorted(headers_to_sign.keys())
        canonical_headers = "".join(f"{k}:{headers_to_sign[k]}\n" for k in sorted_keys)
        signed_headers_str = ";".join(sorted_keys)
        canonical_request = "\n".join(
            [
                method.upper(),
                canonical_uri,
                "",
                canonical_headers,
                signed_headers_str,
                payload_sha256,
            ]
        )

        credential_scope = f"{date_stamp}/{self.region}/s3/aws4_request"
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                credential_scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )
        k_date = _hmac_sha256(f"AWS4{self.secret_key}".encode("utf-8"), date_stamp)
        k_region = _hmac_sha256(k_date, self.region)
        k_service = _hmac_sha256(k_region, "s3")
        k_signing = _hmac_sha256(k_service, "aws4_request")
        signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

        outgoing_headers["Authorization"] = (
            f"AWS4-HMAC-SHA256 Credential={self.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers_str}, Signature={signature}"
        )
        return url, outgoing_headers

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=self.timeout_seconds, transport=self._transport)

    def put_stream(
        self,
        *,
        key: str,
        file_obj: BinaryIO,
        content_type: str,
        size_bytes: int,
        sha256_hex: Optional[str] = None,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> S3PutResult:
        payload_hash = sha256_hex or "UNSIGNED-PAYLOAD"
        headers_map = {
            "Content-Type": content_type,
            "Content-Length": str(size_bytes),
        }
        if extra_headers:
            headers_map.update(extra_headers)
        url, headers = self.signed_headers(
            method="PUT",
            key=key,
            payload_sha256=payload_hash,
            extra_headers=headers_map,
        )
        file_obj.seek(0)

        def _iter_upload() -> Iterator[bytes]:
            while True:
                chunk = file_obj.read(STREAM_CHUNK_BYTES)
                if not chunk:
                    break
                yield chunk

        try:
            with self._client() as client:
                resp = client.put(url, headers=headers, content=_iter_upload())
            if resp.status_code not in (200, 201, 204):
                raise S3ClientError("Object storage rejected upload.")
            return S3PutResult(
                size_bytes=size_bytes,
                content_type=content_type,
                sha256=sha256_hex,
                etag=(resp.headers.get("etag") or "").strip('"') or None,
            )
        except httpx.HTTPError as exc:
            raise S3ClientError("Object storage upload failed.") from exc

    def open_stream(
        self,
        *,
        key: str,
        chunk_size: int = STREAM_CHUNK_BYTES,
    ) -> S3StreamResult:
        url, headers = self.signed_headers(method="GET", key=key, payload_sha256="UNSIGNED-PAYLOAD")
        client = self._client()
        stream_ctx = None
        entered = False
        try:
            stream_ctx = client.stream("GET", url, headers=headers)
            resp = stream_ctx.__enter__()
            entered = True
            if resp.status_code == 404:
                raise S3ObjectNotFoundError("Requested object was not found in object storage.")
            if resp.status_code >= 400:
                raise S3ClientError("Object storage retrieval failed.")

            content_len_raw = resp.headers.get("content-length")
            size_bytes = int(content_len_raw) if content_len_raw and content_len_raw.isdigit() else None
            content_type = resp.headers.get("content-type")

            def _cleanup() -> None:
                try:
                    stream_ctx.__exit__(None, None, None)
                finally:
                    client.close()

            return S3StreamResult(
                chunk_iterator=resp.iter_bytes(chunk_size=chunk_size),
                close_callback=_cleanup,
                size_bytes=size_bytes,
                content_type=content_type,
            )
        except S3ObjectNotFoundError:
            if entered and stream_ctx is not None:
                stream_ctx.__exit__(None, None, None)
            client.close()
            raise
        except httpx.HTTPError as exc:
            if entered and stream_ctx is not None:
                stream_ctx.__exit__(None, None, None)
            client.close()
            raise S3ClientError("Unable to stream object from object storage.") from exc
        except Exception:
            if entered and stream_ctx is not None:
                stream_ctx.__exit__(None, None, None)
            client.close()
            raise

    def head_object(self, *, key: str) -> Optional[S3PutResult]:
        url, headers = self.signed_headers(method="HEAD", key=key, payload_sha256="UNSIGNED-PAYLOAD")
        try:
            with self._client() as client:
                resp = client.head(url, headers=headers)
            if resp.status_code == 404:
                return None
            if resp.status_code >= 400:
                raise S3ClientError("Object storage metadata lookup failed.")
            length_raw = resp.headers.get("content-length")
            size = int(length_raw) if length_raw and length_raw.isdigit() else 0
            return S3PutResult(
                size_bytes=size,
                content_type=resp.headers.get("content-type") or "application/octet-stream",
                etag=(resp.headers.get("etag") or "").strip('"') or None,
            )
        except httpx.HTTPError as exc:
            raise S3ClientError("Object storage metadata lookup failed.") from exc

    def delete_object(self, *, key: str) -> None:
        try:
            url, headers = self.signed_headers(method="DELETE", key=key, payload_sha256="UNSIGNED-PAYLOAD")
            with self._client() as client:
                client.delete(url, headers=headers)
        except Exception:
            pass

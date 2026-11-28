"""Shared PostgreSQL-backed & process-safe rate limiter for authentication and sensitive endpoints.

Why PostgreSQL-backed?
- Multi-worker FastAPI deployments (e.g. Uvicorn/Gunicorn workers) do not share in-process memory.
- Using an atomic `INSERT ... ON CONFLICT DO UPDATE` upsert on `rate_limit_buckets` shares rate-limit
  counters across all backend workers without requiring an external Redis cluster.
- When running inside single-connection rolled-back test fixtures (or if DB is unavailable), falls back
  to a bounded in-memory sliding window so tests remain isolated and rate limiting never fails open.
"""
import hashlib
import hmac
import ipaddress
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import log_db_error, log_security_event


class SharedRateLimiter:
    def __init__(self, max_in_memory_keys: int = 10000) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._max_in_memory_keys = max_in_memory_keys
        self._check_counter = 0

    def _evict_if_needed(self, cutoff: float) -> None:
        if len(self._hits) <= self._max_in_memory_keys:
            return
        stale_keys = [k for k, dq in self._hits.items() if not dq or dq[-1] <= cutoff]
        for k in stale_keys:
            self._hits.pop(k, None)
        if len(self._hits) > self._max_in_memory_keys:
            # Drop oldest keys to cap memory strictly
            for k in list(self._hits.keys())[: len(self._hits) - self._max_in_memory_keys]:
                self._hits.pop(k, None)

    def _check_memory(self, composite_key: str, max_requests: int, window_seconds: int) -> None:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            self._evict_if_needed(cutoff)
            q = self._hits[composite_key]
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= max_requests:
                retry_after = max(1, int(q[0] + window_seconds - now))
                log_security_event(
                    "rate_limit.exceeded",
                    backend="memory",
                    bucket_key=composite_key,
                    retry_after=retry_after,
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please slow down and try again shortly.",
                    headers={"Retry-After": str(retry_after)},
                )
            q.append(now)

    def _check_postgres(
        self,
        engine: Engine,
        composite_key: str,
        max_requests: int,
        window_seconds: int,
    ) -> None:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=window_seconds)

        upsert_sql = text(
            """
            INSERT INTO rate_limit_buckets (bucket_key, window_start, hit_count, updated_at)
            VALUES (:bucket_key, :now, 1, :now)
            ON CONFLICT (bucket_key) DO UPDATE SET
                hit_count = CASE
                    WHEN rate_limit_buckets.window_start <= :cutoff THEN 1
                    ELSE rate_limit_buckets.hit_count + 1
                END,
                window_start = CASE
                    WHEN rate_limit_buckets.window_start <= :cutoff THEN :now
                    ELSE rate_limit_buckets.window_start
                END,
                updated_at = :now
            RETURNING hit_count, window_start
            """
        )

        # Execute on an independent short-lived connection so failed request rollbacks
        # (e.g. invalid password returning 401) do NOT roll back the rate-limit increment.
        with engine.begin() as conn:
            row = conn.execute(
                upsert_sql,
                {"bucket_key": composite_key[:200], "now": now, "cutoff": cutoff},
            ).one()
            hit_count = int(row.hit_count)
            window_start = row.window_start

            # Opportunistic bounded cleanup of expired buckets (~1% of requests)
            if secrets.randbelow(100) == 0:
                stale_before = now - timedelta(hours=24)
                conn.execute(
                    text(
                        """
                        DELETE FROM rate_limit_buckets
                        WHERE bucket_key IN (
                            SELECT bucket_key FROM rate_limit_buckets
                            WHERE updated_at < :stale
                            LIMIT 1000
                        )
                        """
                    ),
                    {"stale": stale_before},
                )

        if hit_count > max_requests:
            elapsed = (now - window_start).total_seconds()
            retry_after = max(1, int(window_seconds - elapsed))
            log_security_event(
                "rate_limit.exceeded",
                backend="postgresql",
                bucket_key=composite_key,
                retry_after=retry_after,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please slow down and try again shortly.",
                headers={"Retry-After": str(retry_after)},
            )

    def check(
        self,
        bucket: str,
        identifier: str,
        max_requests: int,
        window_seconds: int,
        db: Optional[Session] = None,
    ) -> None:
        composite_key = f"{bucket}:{identifier}"
        if settings.RATE_LIMIT_USE_DB and db is not None:
            bind = db.get_bind()
            if isinstance(bind, Engine):
                try:
                    self._check_postgres(bind, composite_key, max_requests, window_seconds)
                    return
                except HTTPException:
                    raise
                except Exception as exc:  # noqa: BLE001
                    log_db_error("rate_limit.postgres_error", bucket=bucket)
                    if settings.is_production:
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Rate-limiting service is temporarily unavailable.",
                        ) from exc

        if settings.is_production:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Distributed rate limiter is required in production.",
            )

        self._check_memory(composite_key, max_requests=max_requests, window_seconds=window_seconds)

    def reset(self, engine: Optional[Engine] = None) -> None:
        with self._lock:
            self._hits.clear()
        if engine is not None:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM rate_limit_buckets"))


rate_limiter = SharedRateLimiter()


def _parse_single_ip(raw_value: str | None) -> str | None:
    """Validate and normalize a single IPv4/IPv6 literal, rejecting multi-value headers."""
    if raw_value is None:
        return None
    cleaned = raw_value.strip()
    if not cleaned or "," in cleaned or any(ch.isspace() for ch in cleaned):
        return None
    try:
        return str(ipaddress.ip_address(cleaned))
    except ValueError:
        return None


def get_client_ip(request: Request) -> str:
    """Extract client IP using fail-closed proxy semantics; never trusts X-Forwarded-For."""
    if not settings.TRUST_PROXY_HEADERS:
        if request.client and request.client.host:
            parsed_peer = _parse_single_ip(request.client.host)
            if parsed_peer is not None:
                return parsed_peer
            stripped_peer = request.client.host.strip()
            return stripped_peer if stripped_peer else "unknown"
        return "unknown"

    if settings.TRUST_CLOUDFLARE_HEADERS:
        cf_connecting_ip = request.headers.get("cf-connecting-ip")
        if cf_connecting_ip is not None:
            parsed_cf = _parse_single_ip(cf_connecting_ip)
            return parsed_cf if parsed_cf is not None else "unknown"

    if request.client and request.client.host:
        parsed_peer = _parse_single_ip(request.client.host)
        if parsed_peer is not None:
            ip_obj = ipaddress.ip_address(parsed_peer)
            if (
                ip_obj.is_global
                and not ip_obj.is_private
                and not ip_obj.is_loopback
                and not ip_obj.is_link_local
                and not ip_obj.is_multicast
                and not ip_obj.is_unspecified
            ):
                return parsed_peer
    return "unknown"


def get_valid_inet_or_none(request: Request) -> str | None:
    """Return a valid IPv4/IPv6 string suitable for PostgreSQL INET column, or None."""
    host = get_client_ip(request)
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        return None


def normalize_rate_limit_identifier(raw_value: str | None, *, kind: str = "generic") -> str | None:
    """Normalize an identifier consistently before hashing for rate-limit keys."""
    if not isinstance(raw_value, str):
        return None
    cleaned = raw_value.strip()
    if not cleaned:
        return None
    if kind in {"email", "username"}:
        return cleaned.lower()
    if kind == "phone":
        compact = re.sub(r"[\s().-]+", "", cleaned)
        return compact or None
    if kind == "token":
        return cleaned
    return cleaned.lower()


def hash_rate_limit_identifier(
    namespace: str,
    raw_value: str | None,
    *,
    kind: str = "generic",
) -> str | None:
    """Return a fixed-width HMAC-SHA256 hex digest for a normalized identifier."""
    normalized = normalize_rate_limit_identifier(raw_value, kind=kind)
    if normalized is None:
        return None
    secret_material = (settings.JWT_SECRET_KEY or "digiverse:rate-limit:fallback").encode("utf-8")
    msg = f"digiverse:rl:v1:{namespace}:{kind}:{normalized}".encode("utf-8")
    return hmac.new(secret_material, msg, hashlib.sha256).hexdigest()


def check_identifier_rate_limit(
    bucket: str,
    identifier: str | None,
    *,
    kind: str = "generic",
    max_requests: int,
    window_seconds: int,
    db: Optional[Session],
) -> None:
    """Enforce a shared rate limit keyed by a domain-separated HMAC-SHA256 digest."""
    digest = hash_rate_limit_identifier(bucket, identifier, kind=kind)
    if digest is None:
        return
    rate_limiter.check(
        bucket,
        f"id:{digest}",
        max_requests=max_requests,
        window_seconds=window_seconds,
        db=db,
    )


def rate_limit(
    bucket: str,
    max_requests: int,
    window_seconds: int,
    *,
    unknown_ip_max_requests: int | None = None,
    unknown_ip_window_seconds: int | None = None,
) -> Callable[[Request, Session], None]:
    """Rate-limit by verified client IP; never pools 'unknown' traffic into a narrow IP bucket."""

    def _dep(request: Request, db: Session = Depends(get_db)) -> None:
        client_ip = get_client_ip(request)
        if client_ip != "unknown":
            rate_limiter.check(
                bucket,
                client_ip,
                max_requests=max_requests,
                window_seconds=window_seconds,
                db=db,
            )
            return
        if unknown_ip_max_requests is not None:
            rate_limiter.check(
                bucket,
                "cb:unknown",
                max_requests=unknown_ip_max_requests,
                window_seconds=unknown_ip_window_seconds or window_seconds,
                db=db,
            )

    return _dep


def rate_limit_customer(
    bucket: str,
    max_requests: int,
    window_seconds: int,
    *,
    ip_max_requests: int | None = None,
    ip_window_seconds: int | None = None,
) -> Callable[..., None]:
    """Rate-limit an authenticated customer endpoint per customer identity using SharedRateLimiter."""
    from app.core.permissions import get_current_customer

    if ip_max_requests is None:

        def _dep(
            customer=Depends(get_current_customer),
            db: Session = Depends(get_db),
        ) -> None:
            rate_limiter.check(
                bucket,
                f"customer:{customer.id}",
                max_requests=max_requests,
                window_seconds=window_seconds,
                db=db,
            )

        return _dep

    def _dep_with_verified_ip(
        request: Request,
        customer=Depends(get_current_customer),
        db: Session = Depends(get_db),
    ) -> None:
        rate_limiter.check(
            bucket,
            f"customer:{customer.id}",
            max_requests=max_requests,
            window_seconds=window_seconds,
            db=db,
        )
        client_ip = get_client_ip(request)
        if client_ip != "unknown":
            rate_limiter.check(
                f"{bucket}:ip",
                client_ip,
                max_requests=ip_max_requests,
                window_seconds=ip_window_seconds or window_seconds,
                db=db,
            )

    return _dep_with_verified_ip

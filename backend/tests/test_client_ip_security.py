"""Regression tests for Stage B.1.3 client IP security hardening."""

import ast
import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.requests import Request
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core import config as config_module
from app.core import rate_limit as rate_limit_module
from app.core.rate_limit import (
    SharedRateLimiter,
    check_identifier_rate_limit,
    get_client_ip,
    get_valid_inet_or_none,
    hash_rate_limit_identifier,
    normalize_rate_limit_identifier,
    rate_limit,
    rate_limit_customer,
    rate_limiter,
)
from app.core.security import (
    ADMIN_ACCESS_COOKIE,
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    CUSTOMER_ACCESS_COOKIE,
    create_customer_access_token,
    get_password_hash,
)
from app.main import app
from app.models.auth import AuthSession
from app.models.enums import AuthSubjectType


REPO_ROOT = Path(__file__).resolve().parents[2]


def _make_request(
    *,
    headers: dict[str, str] | None = None,
    client_host: str | None = "127.0.0.1",
    client_port: int = 12345,
) -> Request:
    raw_headers = [
        (k.lower().encode("latin-1"), v.encode("latin-1"))
        for k, v in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/health",
        "headers": raw_headers,
        "client": (client_host, client_port) if client_host is not None else None,
    }
    return Request(scope)


@pytest.fixture(autouse=True)
def _reset_rate_limiter_state():
    rate_limiter.reset()
    yield
    rate_limiter.reset()


def test_direct_mode_ignores_all_forwarded_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_PROXY_HEADERS", False)
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_CLOUDFLARE_HEADERS", True)

    req = _make_request(
        headers={
            "X-Forwarded-For": "1.2.3.4, 5.6.7.8",
            "CF-Connecting-IP": "9.9.9.9",
        },
        client_host="198.51.100.42",
    )

    assert get_client_ip(req) == "198.51.100.42"


def test_direct_mode_normalizes_ipv6_and_handles_testclient_and_missing_peer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_PROXY_HEADERS", False)

    ipv6_req = _make_request(client_host="2001:0db8:0000:0000:0000:0000:0000:0001")
    testclient_req = _make_request(client_host="testclient")
    missing_req = _make_request(client_host=None)

    assert get_client_ip(ipv6_req) == "2001:db8::1"
    assert get_client_ip(testclient_req) == "testclient"
    assert get_client_ip(missing_req) == "unknown"


def test_proxy_mode_default_fails_closed_for_internal_peer_and_ignores_xff_and_cf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_PROXY_HEADERS", True)
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_CLOUDFLARE_HEADERS", False)

    req = _make_request(
        headers={
            "X-Forwarded-For": "8.8.8.8",
            "CF-Connecting-IP": "1.1.1.1",
        },
        client_host="10.0.0.15",
    )

    assert get_client_ip(req) == "unknown"


@pytest.mark.parametrize(
    ("peer_ip", "expected"),
    [
        ("8.8.8.8", "8.8.8.8"),
        ("2606:4700:4700::1111", "2606:4700:4700::1111"),
        ("127.0.0.1", "unknown"),
        ("10.1.2.3", "unknown"),
        ("172.16.0.1", "unknown"),
        ("192.168.1.50", "unknown"),
        ("169.254.169.254", "unknown"),
        ("0.0.0.0", "unknown"),
        ("::1", "unknown"),
        ("fc00::1", "unknown"),
        ("testclient", "unknown"),
    ],
)
def test_proxy_mode_without_cloudflare_accepts_only_global_peer_ip(
    monkeypatch: pytest.MonkeyPatch,
    peer_ip: str,
    expected: str,
) -> None:
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_PROXY_HEADERS", True)
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_CLOUDFLARE_HEADERS", False)

    req = _make_request(
        headers={"X-Forwarded-For": "1.1.1.1"},
        client_host=peer_ip,
    )
    assert get_client_ip(req) == expected


@pytest.mark.parametrize(
    ("cf_header", "expected"),
    [
        ("1.1.1.1", "1.1.1.1"),
        ("  8.8.4.4  ", "8.8.4.4"),
        ("2606:4700:4700:0000:0000:0000:0000:1111", "2606:4700:4700::1111"),
    ],
)
def test_proxy_mode_cloudflare_opt_in_accepts_single_valid_cf_connecting_ip(
    monkeypatch: pytest.MonkeyPatch,
    cf_header: str,
    expected: str,
) -> None:
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_PROXY_HEADERS", True)
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_CLOUDFLARE_HEADERS", True)

    req = _make_request(
        headers={
            "CF-Connecting-IP": cf_header,
            "X-Forwarded-For": "9.9.9.9, 10.0.0.1",
        },
        client_host="10.0.0.5",
    )

    assert get_client_ip(req) == expected


@pytest.mark.parametrize(
    "bad_cf_header",
    [
        "",
        "   ",
        "1.1.1.1, 8.8.8.8",
        "1.1.1.1 8.8.8.8",
        "not-an-ip",
        "1.1.1.1:8080",
        "8.8.8.8; drop table",
    ],
)
def test_proxy_mode_cloudflare_opt_in_rejects_malformed_or_multi_value_cf_header(
    monkeypatch: pytest.MonkeyPatch,
    bad_cf_header: str,
) -> None:
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_PROXY_HEADERS", True)
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_CLOUDFLARE_HEADERS", True)

    req = _make_request(
        headers={
            "CF-Connecting-IP": bad_cf_header,
            "X-Forwarded-For": "1.1.1.1",
        },
        client_host="10.0.0.5",
    )

    assert get_client_ip(req) == "unknown"


def test_forged_xff_never_used_when_cf_header_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_PROXY_HEADERS", True)
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_CLOUDFLARE_HEADERS", True)

    req = _make_request(
        headers={"X-Forwarded-For": "151.101.1.1"},
        client_host="10.20.30.40",
    )

    assert get_client_ip(req) == "unknown"


def test_get_valid_inet_or_none_handles_valid_and_unknown_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_PROXY_HEADERS", True)
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_CLOUDFLARE_HEADERS", True)

    assert (
        get_valid_inet_or_none(
            _make_request(headers={"CF-Connecting-IP": "1.1.1.1"}, client_host="10.0.0.1")
        )
        == "1.1.1.1"
    )
    assert (
        get_valid_inet_or_none(
            _make_request(
                headers={"CF-Connecting-IP": "2606:4700:4700:0000:0000:0000:0000:1111"},
                client_host="10.0.0.1",
            )
        )
        == "2606:4700:4700::1111"
    )
    assert (
        get_valid_inet_or_none(
            _make_request(headers={"X-Forwarded-For": "8.8.8.8"}, client_host="10.0.0.1")
        )
        is None
    )

    monkeypatch.setattr(rate_limit_module.settings, "TRUST_PROXY_HEADERS", False)
    assert get_valid_inet_or_none(_make_request(client_host="testclient")) is None


def test_rate_limit_blocks_forged_xff_rotation_attack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rate_limit_module.settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_PROXY_HEADERS", True)
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_CLOUDFLARE_HEADERS", True)
    monkeypatch.setattr(rate_limit_module.settings, "RATE_LIMIT_USE_DB", False)

    dep = rate_limit("login_test", max_requests=2, window_seconds=60)

    for idx in range(2):
        dep(
            _make_request(
                headers={
                    "CF-Connecting-IP": "8.8.8.8",
                    "X-Forwarded-For": f"198.51.100.{idx + 1}",
                },
                client_host="10.0.0.5",
            ),
            db=None,
        )

    with pytest.raises(HTTPException) as exc_info:
        dep(
            _make_request(
                headers={
                    "CF-Connecting-IP": "8.8.8.8",
                    "X-Forwarded-For": "198.51.100.99",
                },
                client_host="10.0.0.5",
            ),
            db=None,
        )
    assert exc_info.value.status_code == 429

    # Different real client IP gets an isolated bucket
    dep(
        _make_request(
            headers={
                "CF-Connecting-IP": "1.1.1.1",
                "X-Forwarded-For": "198.51.100.99",
            },
            client_host="10.0.0.5",
        ),
        db=None,
    )


def test_rate_limit_customer_remains_keyed_by_customer_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rate_limit_module.settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(rate_limit_module.settings, "RATE_LIMIT_USE_DB", False)

    dep = rate_limit_customer("seller_apply_test", max_requests=1, window_seconds=60)
    customer = SimpleNamespace(id="cust-123")
    dep(customer=customer, db=None)

    with pytest.raises(HTTPException) as exc_info:
        dep(customer=customer, db=None)
    assert exc_info.value.status_code == 429

    other_customer = SimpleNamespace(id="cust-456")
    dep(customer=other_customer, db=None)


def test_settings_default_proxy_flags_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TRUST_PROXY_HEADERS", raising=False)
    monkeypatch.delenv("TRUST_CLOUDFLARE_HEADERS", raising=False)
    defaults = config_module.Settings(
        _env_file=None,
        DATABASE_URL="postgresql://user:pass@localhost:5432/digiverse",
    )
    assert defaults.TRUST_PROXY_HEADERS is False
    assert defaults.TRUST_CLOUDFLARE_HEADERS is False


def test_deployment_configs_have_no_wildcard_forwarded_allow_ips() -> None:
    target_files = [
        REPO_ROOT / "render.production.yaml",
        REPO_ROOT / "backend" / "Procfile",
        REPO_ROOT / "backend" / "Dockerfile",
    ]
    for path in target_files:
        content = path.read_text(encoding="utf-8")
        assert "--forwarded-allow-ips=*" not in content, f"Wildcard proxy trust found in {path}"
        assert "--forwarded-allow-ips" not in content, f"Unexpected forwarded-allow-ips flag in {path}"
        assert "--proxy-headers" in content, f"Expected --proxy-headers in {path}"


def test_rate_limit_module_contains_no_x_forwarded_for_parsing() -> None:
    source = Path(rate_limit_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    docstring_constants = {
        node.body[0].value
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node not in docstring_constants:
            val = node.value.lower()
            assert "x-forwarded-for" not in val
            assert "forwarded" not in val


# ===========================================================================
# STAGE B.1.3.3 — IDENTIFIER NORMALIZATION, HASHING, UNKNOWN-IP & PROXY TESTS
# ===========================================================================


def test_normalize_rate_limit_identifier_variants_and_malformed() -> None:
    assert normalize_rate_limit_identifier("  Alice@Example.COM  ", kind="email") == "alice@example.com"
    assert normalize_rate_limit_identifier("  Aayan_Admin  ", kind="username") == "aayan_admin"
    assert normalize_rate_limit_identifier(" +91 (987) 654-3210 ", kind="phone") == "+919876543210"
    assert normalize_rate_limit_identifier("  AbCdEf123456  ", kind="token") == "AbCdEf123456"
    assert normalize_rate_limit_identifier(None, kind="email") is None
    assert normalize_rate_limit_identifier("", kind="email") is None
    assert normalize_rate_limit_identifier("   \t\n ", kind="username") is None
    assert normalize_rate_limit_identifier(" -()- ", kind="phone") is None


def test_hash_rate_limit_identifier_deterministic_namespace_scoped_and_bounded() -> None:
    h1 = hash_rate_limit_identifier("customer_login_email", "  Alice@Example.COM ", kind="email")
    h2 = hash_rate_limit_identifier("customer_login_email", "alice@example.com", kind="email")
    h_other_ns = hash_rate_limit_identifier("customer_forgot_email", "alice@example.com", kind="email")
    h_case_token_a = hash_rate_limit_identifier("customer_reset_token", "TokEn_AaBb", kind="token")
    h_case_token_b = hash_rate_limit_identifier("customer_reset_token", "token_aabb", kind="token")

    assert h1 is not None and h1 == h2
    assert len(h1) == 64
    assert h1 != h_other_ns
    assert h_case_token_a != h_case_token_b
    assert "alice" not in h1
    assert hash_rate_limit_identifier("customer_login_email", "   ", kind="email") is None


def test_identifier_rate_limit_never_stores_or_logs_raw_identifiers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rate_limit_module.settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(rate_limit_module.settings, "RATE_LIMIT_USE_DB", False)

    recorded_events: list[dict] = []
    monkeypatch.setattr(
        rate_limit_module,
        "log_security_event",
        lambda event, **kwargs: recorded_events.append({"event": event, **kwargs}),
    )

    raw_email = "PrivateUser99@SensitiveDomain.example"
    raw_phone = "+919876501234"
    raw_username = "SuperSecretAdminName"
    raw_token = "ResetTokSecretValue987654321"

    check_identifier_rate_limit(
        "customer_login_email", raw_email, kind="email", max_requests=1, window_seconds=60, db=None
    )
    check_identifier_rate_limit(
        "customer_register_phone", raw_phone, kind="phone", max_requests=2, window_seconds=60, db=None
    )
    check_identifier_rate_limit(
        "admin_login_username", raw_username, kind="username", max_requests=2, window_seconds=60, db=None
    )
    check_identifier_rate_limit(
        "customer_reset_token", raw_token, kind="token", max_requests=2, window_seconds=60, db=None
    )
    # Malformed empty identifier fails safely without crashing or adding empty key
    check_identifier_rate_limit(
        "customer_login_email", "   ", kind="email", max_requests=1, window_seconds=60, db=None
    )

    with pytest.raises(HTTPException) as exc_info:
        check_identifier_rate_limit(
            "customer_login_email", raw_email, kind="email", max_requests=1, window_seconds=60, db=None
        )
    assert exc_info.value.status_code == 429
    assert int(exc_info.value.headers["Retry-After"]) >= 1

    all_keys = list(rate_limiter._hits.keys())
    assert len(all_keys) == 4
    for key in all_keys:
        assert len(key) <= 200
        for secret in (raw_email, raw_email.lower(), raw_phone, raw_username, raw_username.lower(), raw_token):
            assert secret not in key

    assert recorded_events
    for event in recorded_events:
        serialized = repr(event).lower()
        assert "privateuser99" not in serialized
        assert "sensitivedomain" not in serialized


def test_rate_limit_never_pools_unknown_ip_into_narrow_bucket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rate_limit_module.settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_PROXY_HEADERS", True)
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_CLOUDFLARE_HEADERS", False)
    monkeypatch.setattr(rate_limit_module.settings, "RATE_LIMIT_USE_DB", False)

    dep_no_cb = rate_limit("narrow_test", max_requests=2, window_seconds=60)
    dep_with_cb = rate_limit(
        "cb_test", max_requests=2, window_seconds=60, unknown_ip_max_requests=25, unknown_ip_window_seconds=60
    )

    req_unknown = _make_request(headers={"X-Forwarded-For": "1.2.3.4"}, client_host="10.0.0.5")

    # Without explicit circuit breaker, 'unknown' never creates 'narrow_test:unknown'
    for _ in range(10):
        dep_no_cb(req_unknown, db=None)
    assert "narrow_test:unknown" not in rate_limiter._hits

    # With circuit breaker, narrow limit (2) is skipped cleanly while cb:unknown triggers at 25
    for _ in range(25):
        dep_with_cb(req_unknown, db=None)
    assert "cb_test:unknown" not in rate_limiter._hits
    assert "cb_test:cb:unknown" in rate_limiter._hits

    with pytest.raises(HTTPException) as exc_info:
        dep_with_cb(req_unknown, db=None)
    assert exc_info.value.status_code == 429


def test_rate_limit_customer_with_supplementary_verified_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rate_limit_module.settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(rate_limit_module.settings, "RATE_LIMIT_USE_DB", False)
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_PROXY_HEADERS", True)
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_CLOUDFLARE_HEADERS", False)

    dep = rate_limit_customer(
        "supp_cust",
        max_requests=5,
        window_seconds=60,
        ip_max_requests=2,
        ip_window_seconds=60,
    )
    cust_a = SimpleNamespace(id="cust-aaa")
    cust_b = SimpleNamespace(id="cust-bbb")
    cust_c = SimpleNamespace(id="cust-ccc")
    req_unknown = _make_request(client_host="10.0.0.9")

    # Under unknown IP, customers NEVER collide on a supplementary unknown IP bucket
    for cust in (cust_a, cust_b, cust_c):
        dep(request=req_unknown, customer=cust, db=None)
    assert "supp_cust:ip:unknown" not in rate_limiter._hits

    # Under genuinely verified IP, supplementary verified-IP check enforces 2/min
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_CLOUDFLARE_HEADERS", True)
    req_verified = _make_request(headers={"CF-Connecting-IP": "8.8.8.8"}, client_host="10.0.0.9")
    dep(request=req_verified, customer=cust_a, db=None)
    dep(request=req_verified, customer=cust_b, db=None)
    with pytest.raises(HTTPException) as exc_info:
        dep(request=req_verified, customer=cust_c, db=None)
    assert exc_info.value.status_code == 429


def _run_proxy_middleware(
    *,
    trusted_hosts: str | list[str] = "127.0.0.1",
    client: tuple[str, int] | None,
    headers: list[tuple[bytes, bytes]],
    scheme: str = "http",
) -> dict:
    captured_scope: dict = {}

    async def capture_app(scope, receive, send):
        captured_scope.update(scope)

    async def empty_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def empty_send(message):
        return None

    middleware = ProxyHeadersMiddleware(capture_app, trusted_hosts=trusted_hosts)
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": scheme,
        "path": "/api/health",
        "raw_path": b"/api/health",
        "query_string": b"",
        "headers": headers,
        "client": client,
        "server": ("digi-verse-backend.onrender.com", 80),
    }
    asyncio.run(middleware(scope, empty_receive, empty_send))
    return captured_scope


def test_uvicorn_proxy_headers_middleware_preserves_untrusted_internal_peer_and_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_PROXY_HEADERS", True)
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_CLOUDFLARE_HEADERS", False)

    captured = _run_proxy_middleware(
        trusted_hosts="127.0.0.1",
        client=("10.0.0.5", 44321),
        headers=[
            (b"x-forwarded-for", b"1.2.3.4, 10.0.0.5"),
            (b"x-forwarded-proto", b"https"),
        ],
    )

    # Uvicorn default trusted_hosts='127.0.0.1' does NOT trust internal proxy 10.0.0.5
    assert captured["client"] == ("10.0.0.5", 44321)
    assert captured["scheme"] == "http"

    # FastAPI IP extraction still refuses forged X-Forwarded-For and fails closed on internal peer
    assert get_client_ip(Request(captured)) == "unknown"


def test_uvicorn_proxy_headers_middleware_trusted_peer_vs_app_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _run_proxy_middleware(
        trusted_hosts="127.0.0.1",
        client=("127.0.0.1", 55000),
        headers=[
            (b"x-forwarded-for", b"8.8.8.8, 127.0.0.1"),
            (b"x-forwarded-proto", b"https"),
        ],
    )
    assert captured["client"] == ("8.8.8.8", 0)
    assert captured["scheme"] == "https"

    # Without TRUST_PROXY_HEADERS=True, forwarded rewriting stays ignored at app boundary unless trusted
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_PROXY_HEADERS", True)
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_CLOUDFLARE_HEADERS", False)
    # ProxyHeadersMiddleware only trusted 127.0.0.1; internal proxy peers like 10.0.0.5 are never rewritten
    assert get_client_ip(Request(captured)) == "8.8.8.8"

    untrusted_render_peer = _run_proxy_middleware(
        trusted_hosts="127.0.0.1",
        client=("10.20.30.40", 55000),
        headers=[(b"x-forwarded-for", b"8.8.8.8")],
    )
    assert untrusted_render_peer["client"] == ("10.20.30.40", 55000)
    assert get_client_ip(Request(untrusted_render_peer)) == "unknown"


def test_uvicorn_proxy_headers_middleware_handles_missing_and_malformed_headers_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_PROXY_HEADERS", True)
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_CLOUDFLARE_HEADERS", False)

    missing_client = _run_proxy_middleware(
        trusted_hosts="127.0.0.1",
        client=None,
        headers=[(b"x-forwarded-for", b"1.1.1.1")],
    )
    assert missing_client["client"] is None
    assert get_client_ip(Request(missing_client)) == "unknown"

    malformed = _run_proxy_middleware(
        trusted_hosts="127.0.0.1",
        client=("127.0.0.1", 1234),
        headers=[
            (b"x-forwarded-for", b""),
            (b"x-forwarded-proto", b"javascript"),
        ],
    )
    assert malformed["client"] == ("127.0.0.1", 1234)
    assert malformed["scheme"] == "http"
    assert get_client_ip(Request(malformed)) == "unknown"


def _set_unknown_proxy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_PROXY_HEADERS", True)
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_CLOUDFLARE_HEADERS", False)


def test_unknown_ip_customer_login_isolation_and_anti_enumeration(
    api_client: TestClient,
    db: Session,
    make_customer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_unknown_proxy_env(monkeypatch)
    password = "StrongPass#2026"
    customer_b = make_customer(
        email=f"cust-b-{uuid.uuid4().hex[:8]}@example.test",
        password_hash=get_password_hash(password),
    )
    victim_email = f"victim-{uuid.uuid4().hex[:8]}@example.test"

    # Exhaust customer_login_email bucket for victim_email behind unknown IP (15 allowed, 16th -> 429)
    for idx in range(15):
        res = api_client.post(
            "/api/auth/login",
            json={"email": victim_email if idx % 2 == 0 else victim_email.upper(), "password": "WrongPass#123"},
            headers={"X-Forwarded-For": f"198.51.100.{idx + 1}"},
        )
        assert res.status_code == 401

    blocked = api_client.post(
        "/api/auth/login",
        json={"email": victim_email, "password": "WrongPass#123"},
    )
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1

    # Unrelated user behind the exact same proxy ('unknown') is NOT blocked and receives cookies + CSRF
    ok_res = api_client.post(
        "/api/auth/login",
        json={"email": customer_b.email, "password": password},
    )
    assert ok_res.status_code == 200
    assert CUSTOMER_ACCESS_COOKIE in ok_res.cookies
    assert CSRF_COOKIE_NAME in ok_res.cookies


def test_unknown_ip_admin_login_isolation_and_cookie_preservation(
    api_client: TestClient,
    make_admin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_unknown_proxy_env(monkeypatch)
    admin_password = "AdminStrong#2026!"
    admin_b = make_admin(
        username=f"admin_b_{uuid.uuid4().hex[:6]}",
        password_hash=get_password_hash(admin_password),
        must_change_password=False,
    )
    targeted_username = f"target_adm_{uuid.uuid4().hex[:6]}"

    for idx in range(15):
        res = api_client.post(
            "/api/admin/auth/login",
            json={
                "username": targeted_username if idx % 2 == 0 else targeted_username.upper(),
                "password": "WrongPassword#1",
            },
            headers={"X-Forwarded-For": f"203.0.113.{idx + 1}"},
        )
        assert res.status_code == 401

    blocked = api_client.post(
        "/api/admin/auth/login",
        json={"username": targeted_username, "password": "WrongPassword#1"},
    )
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1

    ok_res = api_client.post(
        "/api/admin/auth/login",
        json={"username": admin_b.username, "password": admin_password},
    )
    assert ok_res.status_code == 200
    assert ADMIN_ACCESS_COOKIE in ok_res.cookies
    set_cookies = [h.lower() for h in ok_res.headers.get_list("set-cookie")]
    assert any(ADMIN_ACCESS_COOKIE.lower() in h and "samesite=strict" in h for h in set_cookies)


def test_unknown_ip_forgot_and_reset_password_isolation(
    api_client: TestClient,
    make_customer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_unknown_proxy_env(monkeypatch)
    known_user = make_customer(email=f"known-{uuid.uuid4().hex[:8]}@example.test")
    unknown_target = f"missing-{uuid.uuid4().hex[:8]}@example.test"

    # Both known and unknown targets allow 5/300s then return identical 429 without enumeration
    for _ in range(5):
        r_unknown = api_client.post("/api/auth/forgot-password", json={"email": unknown_target})
        assert r_unknown.status_code == 200
    assert api_client.post("/api/auth/forgot-password", json={"email": unknown_target}).status_code == 429

    # Completely independent customer email remains unblocked behind same 'unknown' proxy
    r_known = api_client.post("/api/auth/forgot-password", json={"email": known_user.email})
    assert r_known.status_code == 200
    assert "reset instructions" in r_known.json()["message"].lower()

    # Reset-password hashes token and isolates per token
    token_a = "reset-token-secret-" + uuid.uuid4().hex
    token_b = "reset-token-secret-" + uuid.uuid4().hex
    for _ in range(5):
        r_tok = api_client.post(
            "/api/auth/reset-password",
            json={"token": token_a, "new_password": "NewStrongPass#2026"},
        )
        assert r_tok.status_code == 400
    r_tok_limited = api_client.post(
        "/api/auth/reset-password",
        json={"token": token_a, "new_password": "NewStrongPass#2026"},
    )
    assert r_tok_limited.status_code == 429

    # Different token still reaches token validation instead of sharing token_a's bucket
    r_tok_b = api_client.post(
        "/api/auth/reset-password",
        json={"token": token_b, "new_password": "NewStrongPass#2026"},
    )
    assert r_tok_b.status_code == 400


def test_unknown_ip_registration_identifier_isolation_and_privacy(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_unknown_proxy_env(monkeypatch)
    # Also simulate anonymous repeated attempts against the same phone / email
    fixed_email = f"spam-{uuid.uuid4().hex[:8]}@example.test"
    fixed_phone = f"+9197{str(uuid.uuid4().int)[:8]}"

    # First succeeds, next 4 hit existing conflict/409, 6th hits 429 per identifier
    first = api_client.post(
        "/api/auth/register",
        json={
            "full_name": "First User",
            "email": fixed_email,
            "phone_number": fixed_phone,
            "password": "StrongPass#2026",
        },
    )
    assert first.status_code == 201
    for idx in range(4):
        dup = api_client.post(
            "/api/auth/register",
            json={
                "full_name": "Dup User",
                "email": fixed_email,
                "phone_number": f"+9196{str(uuid.uuid4().int)[:8]}",
                "password": "StrongPass#2026",
            },
        )
        assert dup.status_code == 409

    blocked = api_client.post(
        "/api/auth/register",
        json={
            "full_name": "Blocked User",
            "email": fixed_email,
            "phone_number": f"+9195{str(uuid.uuid4().int)[:8]}",
            "password": "StrongPass#2026",
        },
    )
    assert blocked.status_code == 429

    # Another legitimate visitor on the same 'unknown' proxy can register normally
    api_client.cookies.clear()
    other = api_client.post(
        "/api/auth/register",
        json={
            "full_name": "Clean Visitor",
            "email": f"clean-{uuid.uuid4().hex[:8]}@example.test",
            "phone_number": f"+9194{str(uuid.uuid4().int)[:8]}",
            "password": "StrongPass#2026",
        },
    )
    assert other.status_code == 201


def _bearer_for_customer(db: Session, customer) -> dict[str, str]:
    sess = AuthSession(
        subject_type=AuthSubjectType.CUSTOMER,
        customer_id=customer.id,
        refresh_token_hash=uuid.uuid4().hex + uuid.uuid4().hex,
        family_id=uuid.uuid4(),
        ip_address="unknown",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(sess)
    db.flush()
    tok = create_customer_access_token(customer.id, sess.id)
    return {"Authorization": f"Bearer {tok}"}


def test_unknown_ip_authenticated_otp_checkout_and_download_isolation(
    api_client: TestClient,
    db: Session,
    make_customer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_unknown_proxy_env(monkeypatch)
    monkeypatch.setattr(rate_limit_module.settings, "OTP_DELIVERY_PROVIDER", "development")
    monkeypatch.setattr(rate_limit_module.settings, "ENABLE_DEV_OTP", True)

    cust_a = make_customer(phone_number=f"+9193{str(uuid.uuid4().int)[:8]}", is_phone_verified=False)
    cust_b = make_customer(phone_number=f"+9192{str(uuid.uuid4().int)[:8]}", is_phone_verified=False)
    headers_a = _bearer_for_customer(db, cust_a)
    headers_b = _bearer_for_customer(db, cust_b)

    # Unauthenticated caller fails closed at 401 without touching customer buckets
    assert api_client.post("/api/auth/otp/send").status_code == 401

    # Customer A hits 10/min OTP send route limit -> 11th returns 429; Customer B unaffected!
    # Keep OTP_MAX_SENDS_PER_WINDOW high locally so route limiter 429 is isolated
    monkeypatch.setattr(rate_limit_module.settings, "OTP_MAX_SENDS_PER_WINDOW", 20)
    for _ in range(10):
        assert api_client.post("/api/auth/otp/send", headers=headers_a).status_code == 200
    assert api_client.post("/api/auth/otp/send", headers=headers_a).status_code == 429
    assert api_client.post("/api/auth/otp/send", headers=headers_b).status_code == 200

    # Customer C exhausts OTP verify route limit (15/min) -> 16th returns route 429; Customer B unaffected!
    cust_c = make_customer(phone_number=f"+9191{str(uuid.uuid4().int)[:8]}", is_phone_verified=False)
    headers_c = _bearer_for_customer(db, cust_c)
    for _ in range(15):
        r_ver = api_client.post("/api/auth/otp/verify", json={"otp_code": "000000"}, headers=headers_c)
        assert r_ver.status_code == 400
    r_ver_limited = api_client.post("/api/auth/otp/verify", json={"otp_code": "000000"}, headers=headers_c)
    assert r_ver_limited.status_code == 429
    assert int(r_ver_limited.headers["Retry-After"]) >= 1
    assert api_client.post("/api/auth/otp/verify", json={"otp_code": "000000"}, headers=headers_b).status_code == 400

    # Customer A hits 30/min checkout limit -> 31st returns 429; Customer B unaffected!
    for _ in range(30):
        r_chk = api_client.post("/api/checkout", headers=headers_a)
        assert r_chk.status_code != 429
    assert api_client.post("/api/checkout", headers=headers_a).status_code == 429
    assert api_client.post("/api/checkout", headers=headers_b).status_code != 429

    # Customer A hits 30/min download grant limit -> 31st returns 429; Customer B unaffected!
    fake_item_id = uuid.uuid4()
    for _ in range(30):
        r_dl = api_client.post(f"/api/downloads/{fake_item_id}", headers=headers_a)
        assert r_dl.status_code != 429
    assert api_client.post(f"/api/downloads/{fake_item_id}", headers=headers_a).status_code == 429
    assert api_client.post(f"/api/downloads/{fake_item_id}", headers=headers_b).status_code != 429


def test_postgres_concurrent_identifier_rate_limit_atomicity(engine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rate_limit_module.settings, "RATE_LIMIT_USE_DB", True)
    rate_limiter.reset(engine=engine)
    bucket = f"conc_id_{uuid.uuid4().hex[:8]}"
    email = f"concurrent-{uuid.uuid4().hex[:8]}@example.test"

    def _hit(_idx: int) -> int:
        with Session(bind=engine) as sess:
            try:
                check_identifier_rate_limit(
                    bucket, email, kind="email", max_requests=5, window_seconds=60, db=sess
                )
                return 200
            except HTTPException as exc:
                return exc.status_code

    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(_hit, range(8)))
        assert results.count(200) == 5
        assert results.count(429) == 3
    finally:
        rate_limiter.reset(engine=engine)


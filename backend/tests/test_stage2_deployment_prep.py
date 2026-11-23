"""Stage 2 Production Deployment Preparation Tests (zero external network, zero DB mutations)."""
from __future__ import annotations

import io
import json
import re
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import HTTPException, Response, UploadFile

from app.api.routes import auth as auth_routes
from app.api.routes import public_catalog
from app.core.config import Settings, build_postgres_connect_args, normalize_postgres_url, settings
from app.core.permissions import require_verified_customer
from app.core.security import (
    ADMIN_ACCESS_COOKIE,
    CSRF_COOKIE_NAME,
    CUSTOMER_ACCESS_COOKIE,
    set_admin_auth_cookies,
    set_customer_auth_cookies,
)
from app.models.customer import Customer
from app.models.enums import OTPPurpose
from app.services import customer_auth_service
from app.services.asset_storage_service import (
    AssetStorageError,
    DisabledPrivateAssetStorageProvider,
    LocalPrivateAssetStorageProvider,
    S3PrivateAssetStorageProvider,
    get_asset_storage,
)
from app.services.commerce_service import _resolve_public_key_id
from app.services.email_service import (
    DisabledEmailProvider,
    EmailDeliveryError,
    get_email_provider,
)
from app.services.payment_gateway import (
    DisabledPaymentProvider,
    MockPaymentProvider,
    RazorpayPaymentProvider,
    get_payment_provider,
)
from app.services.sms_service import (
    DisabledSMSProvider,
    get_sms_provider,
)
from app.services.s3_client import S3ClientError, S3SigV4Client
from app.services.storage_service import (
    DisabledImageStorageProvider,
    LocalImageStorageProvider,
    S3ImageStorageProvider,
    get_image_storage,
)
from app.services.whatsapp_service import (
    DisabledWhatsAppProvider,
    WhatsAppDeliveryError,
    get_whatsapp_provider,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PNG_MAGIC_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + (b"\x00" * 16)


def _minimal_prod_kwargs(**overrides) -> dict:
    data = {
        "ENVIRONMENT": "production",
        "DEBUG": False,
        "DATABASE_URL": "postgresql://prod_u:Secret%231@dpg-render123-a/digiverse_prod?application_name=api",
        "DB_SSLMODE": "require",
        "JWT_SECRET_KEY": "x" * 64,
        "ADMIN_JWT_SECRET_KEY": "y" * 64,
        "COOKIE_SECURE": True,
        "COOKIE_DOMAIN": None,
        "TRUST_PROXY_HEADERS": True,
        "RATE_LIMIT_USE_DB": True,
        "CORS_ORIGINS": ["https://digiverse-store.vercel.app"],
        "ALLOWED_HOSTS": ["digiverse-api.onrender.com"],
        "PAYMENTS_ENABLED": False,
        "PAYMENT_PROVIDER": "disabled",
        "ASSET_STORAGE_BACKEND": "disabled",
        "IMAGE_STORAGE_BACKEND": "disabled",
        "EMAIL_ENABLED": False,
        "OTP_DELIVERY_PROVIDER": "disabled",
        "ENABLE_DEV_OTP": False,
        "WHATSAPP_OTP_ENABLED": False,
    }
    data.update(overrides)
    return data


def _make_settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


# ---------------------------------------------------------------------------
# 1. PostgreSQL URL Normalization & TLS Enforcement
# ---------------------------------------------------------------------------


def test_postgres_url_normalization_preserves_query_params_and_render_hosts():
    assert (
        normalize_postgres_url("postgres://u:p@dpg-abc123-a/digiverse?sslmode=require&connect_timeout=5")
        == "postgresql+psycopg://u:p@dpg-abc123-a/digiverse?sslmode=require&connect_timeout=5"
    )
    assert (
        normalize_postgres_url("POSTGRESQL://u:p@db.render.com:5432/appdb?options=-csearch_path%3Dpublic")
        == "postgresql+psycopg://u:p@db.render.com:5432/appdb?options=-csearch_path%3Dpublic"
    )
    assert (
        normalize_postgres_url("postgresql+psycopg://u:p@localhost:5432/digiverse_test")
        == "postgresql+psycopg://u:p@localhost:5432/digiverse_test"
    )
    assert normalize_postgres_url(None) is None

    s = _make_settings(
        DATABASE_URL="postgres://u:secretpw@dpg-abc123-a/digiverse_prod?sslmode=require",
        TEST_DATABASE_URL="postgresql://u:secretpw@localhost:5432/digiverse_test",
    )
    assert s.DATABASE_URL == "postgresql+psycopg://u:secretpw@dpg-abc123-a/digiverse_prod?sslmode=require"
    assert s.TEST_DATABASE_URL == "postgresql+psycopg://u:secretpw@localhost:5432/digiverse_test"


def test_tls_enforcement_supports_render_internal_url_and_blocks_insecure():
    s_render_internal = _make_settings(**_minimal_prod_kwargs())
    assert s_render_internal.DATABASE_URL.startswith("postgresql+psycopg://")
    assert "application_name=api" in s_render_internal.DATABASE_URL
    assert s_render_internal.validate_production_readiness() == []

    args_with_env_ssl = build_postgres_connect_args(
        s_render_internal.DATABASE_URL,
        db_sslmode="require",
        connect_timeout=5,
    )
    assert args_with_env_ssl == {"connect_timeout": 5, "sslmode": "require"}

    args_url_wins = build_postgres_connect_args(
        "postgresql+psycopg://u:p@host/db?sslmode=verify-full",
        db_sslmode="require",
        connect_timeout=5,
    )
    assert args_url_wins == {"connect_timeout": 5}

    s_missing_tls = _make_settings(**_minimal_prod_kwargs(DB_SSLMODE=None))
    issues = s_missing_tls.validate_production_readiness()
    assert any("TLS" in i for i in issues)
    assert "Secret%231" not in " ".join(issues)


# ---------------------------------------------------------------------------
# 2. Production Integration Readiness, Razorpay States & Payment Disabled
# ---------------------------------------------------------------------------


def test_production_readiness_with_optional_integrations_disabled_and_strict_core_enforced():
    s_min = _make_settings(**_minimal_prod_kwargs())
    assert s_min.validate_production_readiness() == []

    # Local storage must STILL be blocked even when optional integrations are disabled
    s_local_img = _make_settings(**_minimal_prod_kwargs(IMAGE_STORAGE_BACKEND="local"))
    assert any("IMAGE_STORAGE_BACKEND" in i for i in s_local_img.validate_production_readiness())

    s_local_asset = _make_settings(**_minimal_prod_kwargs(ASSET_STORAGE_BACKEND="local"))
    assert any("ASSET_STORAGE_BACKEND" in i for i in s_local_asset.validate_production_readiness())

    # Mock payments must ALWAYS be blocked
    s_mock = _make_settings(**_minimal_prod_kwargs(PAYMENT_PROVIDER="mock"))
    assert any("mock" in i.lower() for i in s_mock.validate_production_readiness())


def test_payment_provider_states_and_fail_closed_behavior(monkeypatch):
    s_disabled_with_test_keys = _make_settings(
        **_minimal_prod_kwargs(
            PAYMENTS_ENABLED=False,
            PAYMENT_PROVIDER="disabled",
            RAZORPAY_KEY_ID="rzp_test_only123",
            RAZORPAY_KEY_SECRET="test_secret_value",
        )
    )
    assert s_disabled_with_test_keys.get_payment_provider_state() == "disabled"
    assert s_disabled_with_test_keys.validate_production_readiness() == []

    s_test_mode_non_prod = _make_settings(
        ENVIRONMENT="staging",
        DEBUG=False,
        DATABASE_URL="postgresql://u:p@staging-db/db?sslmode=require",
        PAYMENTS_ENABLED=True,
        PAYMENT_PROVIDER="razorpay",
        RAZORPAY_KEY_ID="rzp_test_only123",
        RAZORPAY_KEY_SECRET="test_secret_value",
    )
    assert s_test_mode_non_prod.get_payment_provider_state() == "test"

    s_live_mode = _make_settings(
        **_minimal_prod_kwargs(
            PAYMENTS_ENABLED=True,
            PAYMENT_PROVIDER="razorpay",
            RAZORPAY_KEY_ID="rzp_live_123456",
            RAZORPAY_KEY_SECRET="live_secret_value",
            RAZORPAY_WEBHOOK_SECRET="live_wh_secret",
        )
    )
    assert s_live_mode.get_payment_provider_state() == "live"

    # Runtime safeguard: in production with only rzp_test_*, checkout fails 503 via DisabledPaymentProvider
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "PAYMENTS_ENABLED", True)
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "razorpay")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_only123")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "test_secret_value")

    provider = get_payment_provider()
    assert isinstance(provider, DisabledPaymentProvider)
    with pytest.raises(HTTPException) as exc_create:
        provider.create_order("DV-1", Decimal("100.00"), "INR")
    assert exc_create.value.status_code == 503

    with pytest.raises(HTTPException) as exc_verify:
        provider.verify_payment_signature("order_1", "pay_1", "sig")
    assert exc_verify.value.status_code == 503

    with pytest.raises(HTTPException) as exc_wh:
        provider.verify_webhook_signature(b"{}", "sig")
    assert exc_wh.value.status_code == 503

    with pytest.raises(HTTPException) as exc_pub:
        _resolve_public_key_id(provider)
    assert exc_pub.value.status_code == 503

    # Mock payments in production are rejected with 503 / RuntimeError
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "mock")
    with pytest.raises(HTTPException) as exc_mock:
        get_payment_provider()
    assert exc_mock.value.status_code == 503
    with pytest.raises(RuntimeError):
        MockPaymentProvider().create_order("DV-2", Decimal("50.00"), "INR")


# ---------------------------------------------------------------------------
# 3. R2 Public Image & Private Asset Storage Separation
# ---------------------------------------------------------------------------


def test_production_never_falls_back_to_local_storage(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "IMAGE_STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "ASSET_STORAGE_BACKEND", "local")

    with pytest.raises(HTTPException) as exc_img:
        get_image_storage()
    assert exc_img.value.status_code == 503

    with pytest.raises(AssetStorageError):
        get_asset_storage()

    monkeypatch.setattr(settings, "IMAGE_STORAGE_BACKEND", "disabled")
    monkeypatch.setattr(settings, "ASSET_STORAGE_BACKEND", "disabled")
    assert isinstance(get_image_storage(), DisabledImageStorageProvider)
    assert isinstance(get_asset_storage(), DisabledPrivateAssetStorageProvider)

    with pytest.raises(HTTPException) as exc_img_dis:
        get_image_storage().open_image("0" * 32 + ".png")
    assert exc_img_dis.value.status_code == 503

    # Development/test keeps local storage working
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "IMAGE_STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "ASSET_STORAGE_BACKEND", "local")
    assert isinstance(get_image_storage(), LocalImageStorageProvider)
    assert isinstance(get_asset_storage(), LocalPrivateAssetStorageProvider)


def test_r2_public_image_provider_upload_stream_delete_and_bucket_separation(monkeypatch):
    monkeypatch.setattr(settings, "ASSET_STORAGE_BUCKET", "digiverse-private-assets")
    monkeypatch.setattr(settings, "IMAGE_STORAGE_BUCKET", "digiverse-private-assets")

    with pytest.raises(HTTPException) as exc_same_bucket:
        S3ImageStorageProvider(
            bucket="digiverse-private-assets",
            region="auto",
            endpoint_url="https://acct.r2.cloudflarestorage.com",
            access_key="r2_ak",
            secret_key="r2_sk",
        )
    assert exc_same_bucket.value.status_code == 503

    s_same_bucket = _make_settings(
        **_minimal_prod_kwargs(
            ASSET_STORAGE_BACKEND="s3",
            ASSET_STORAGE_BUCKET="shared-bucket",
            ASSET_STORAGE_ACCESS_KEY="ak_real_value",
            ASSET_STORAGE_SECRET_KEY="sk_real_value",
            ASSET_STORAGE_ENDPOINT_URL="https://acct.r2.cloudflarestorage.com",
            IMAGE_STORAGE_BACKEND="s3",
            IMAGE_STORAGE_BUCKET="shared-bucket",
            IMAGE_STORAGE_ACCESS_KEY="img_ak_real_value",
            IMAGE_STORAGE_SECRET_KEY="img_sk_real_value",
            IMAGE_STORAGE_ENDPOINT_URL="https://img-acct.r2.cloudflarestorage.com",
        )
    )
    assert any("separate from ASSET_STORAGE_BUCKET" in i for i in s_same_bucket.validate_production_readiness())

    objects: dict[str, tuple[bytes, str]] = {}

    def _mock_handler(request: httpx.Request) -> httpx.Response:
        key = request.url.path.lstrip("/")
        if request.method == "PUT":
            objects[key] = (request.read(), request.headers.get("Content-Type", "image/png"))
            return httpx.Response(200, headers={"ETag": '"etag123"'})
        if request.method == "GET":
            if key not in objects:
                return httpx.Response(404)
            body, ctype = objects[key]
            return httpx.Response(
                200,
                content=body,
                headers={"Content-Type": ctype, "Content-Length": str(len(body))},
            )
        if request.method == "DELETE":
            objects.pop(key, None)
            return httpx.Response(204)
        return httpx.Response(405)

    img_provider = S3ImageStorageProvider(
        bucket="digiverse-public-images",
        region="auto",
        endpoint_url="https://acct.r2.cloudflarestorage.com",
        access_key="r2_img_ak",
        secret_key="r2_img_sk",
        prefix="public-images",
        transport=httpx.MockTransport(_mock_handler),
    )
    upload = UploadFile(
        file=io.BytesIO(PNG_MAGIC_BYTES),
        filename="banner.png",
        headers={"content-type": "image/png"},
    )
    image_url = img_provider.save_image(upload)
    assert image_url.startswith("/api/uploads/images/")
    filename = image_url.rsplit("/", 1)[-1]
    assert f"digiverse-public-images/public-images/{filename}" in objects

    # Streaming via API route preserves existing URL and headers without exposing R2 keys/endpoint
    monkeypatch.setattr(public_catalog, "get_image_storage", lambda: img_provider)
    stream_resp = public_catalog.serve_uploaded_image(filename)
    assert stream_resp.media_type == "image/png"
    assert stream_resp.headers["X-Content-Type-Options"] == "nosniff"
    assert stream_resp.headers["Content-Disposition"] == "inline"
    assert b"".join(img_provider.open_image(filename).iter_chunks()) == PNG_MAGIC_BYTES
    stream_resp.body_iterator.aclose() if hasattr(stream_resp.body_iterator, "aclose") else None

    img_provider.delete_image(image_url)
    assert f"digiverse-public-images/public-images/{filename}" not in objects

    # Private asset S3 provider stays strictly separate
    priv = S3PrivateAssetStorageProvider(
        bucket="digiverse-private-assets",
        region="auto",
        endpoint_url="https://acct.r2.cloudflarestorage.com",
        access_key="r2_priv_ak",
        secret_key="r2_priv_sk",
        transport=httpx.MockTransport(_mock_handler),
    )
    assert priv.bucket != img_provider.bucket


# ---------------------------------------------------------------------------
# 4. Optional Email (Resend) & WhatsApp OTP Behavior
# ---------------------------------------------------------------------------


def test_disabled_email_and_whatsapp_providers_fail_honestly(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "EMAIL_ENABLED", False)
    monkeypatch.setattr(settings, "OTP_DELIVERY_PROVIDER", "disabled")
    monkeypatch.setattr(settings, "WHATSAPP_OTP_ENABLED", False)

    email_prov = get_email_provider()
    assert isinstance(email_prov, DisabledEmailProvider)
    with pytest.raises(EmailDeliveryError) as exc_mail:
        email_prov.send_transactional_email("a@b.test", "t", "sub", "body")
    assert exc_mail.value.code == "email_disabled"
    assert exc_mail.value.retryable is False

    # Password reset fails honestly (503) instead of pretending reset email was sent
    mock_db = MagicMock()
    with pytest.raises(HTTPException) as exc_reset:
        customer_auth_service.initiate_forgot_password(mock_db, "user@example.test", "1.2.3.4")
    assert exc_reset.value.status_code == 503
    mock_db.scalar.assert_not_called()

    # WhatsApp OTP disabled returns honest disabled status & blocks verified-only access
    sms_prov = get_sms_provider()
    assert isinstance(sms_prov, DisabledSMSProvider)
    res = sms_prov.send_otp("+919876543210", "123456", 5)
    assert res.status == "disabled"
    assert res.provider == "disabled"

    # Explicit /otp/send route fails honestly with 503 when disabled
    dummy_customer = Customer(
        full_name="Test Buyer",
        email="buyer@example.test",
        phone_number="+919876543210",
        password_hash="hash",
        is_phone_verified=False,
    )
    with pytest.raises(HTTPException) as exc_otp_send:
        auth_routes.send_phone_otp(customer=dummy_customer, db=mock_db)
    assert exc_otp_send.value.status_code == 503

    # Security verification gate stays intact (unverified customer -> 403)
    with pytest.raises(HTTPException) as exc_verified_gate:
        require_verified_customer(customer=dummy_customer)
    assert exc_verified_gate.value.status_code == 403

    # WhatsApp marketing dispatch fails honestly when disabled
    wa_prov = get_whatsapp_provider()
    assert isinstance(wa_prov, DisabledWhatsAppProvider)
    with pytest.raises(WhatsAppDeliveryError) as exc_wa:
        wa_prov.send_template_message("+919876543210", "tpl", "hi")
    assert exc_wa.value.code == "whatsapp_disabled"
    assert exc_wa.value.retryable is False

    # OTP challenge issuance when disabled creates no DB rows
    ch, otp_res = customer_auth_service.issue_phone_otp_challenge(
        mock_db, dummy_customer, "+919876543210", OTPPurpose.PHONE_VERIFY
    )
    assert ch is None
    assert otp_res.status == "disabled"
    mock_db.add.assert_not_called()


# ---------------------------------------------------------------------------
# 5. Auth Cookies, Host-Only Policy & Frontend Vercel Routing Integrity
# ---------------------------------------------------------------------------


def _resolve_vercel_cache_control(header_rules: list[dict], path: str) -> str | None:
    """Resolve effective Cache-Control under sequential vercel.json header rule order."""
    val = None
    for rule in header_rules:
        if re.match("^" + rule["source"] + "$", path):
            for hdr in rule["headers"]:
                if hdr["key"].lower() == "cache-control":
                    val = hdr["value"]
    return val


def test_cookie_security_attributes_and_vercel_json_routing_preserved(monkeypatch):
    monkeypatch.setattr(settings, "COOKIE_SECURE", True)
    monkeypatch.setattr(settings, "COOKIE_DOMAIN", None)

    cust_resp = Response()
    csrf_cust = set_customer_auth_cookies(cust_resp, "cust_access", "cust_refresh")
    assert csrf_cust
    set_cookies_cust = cust_resp.headers.getlist("set-cookie")
    cust_access_hdr = next(c for c in set_cookies_cust if c.startswith(f"{CUSTOMER_ACCESS_COOKIE}="))
    csrf_hdr = next(c for c in set_cookies_cust if c.startswith(f"{CSRF_COOKIE_NAME}="))
    assert "HttpOnly" in cust_access_hdr
    assert "Secure" in cust_access_hdr
    assert "samesite=lax" in cust_access_hdr.lower()
    assert "domain=" not in cust_access_hdr.lower()
    assert "httponly" not in csrf_hdr.lower()
    assert "secure" in csrf_hdr.lower()

    admin_resp = Response()
    csrf_admin = set_admin_auth_cookies(admin_resp, "adm_access", "adm_refresh")
    assert csrf_admin
    set_cookies_admin = admin_resp.headers.getlist("set-cookie")
    adm_access_hdr = next(c for c in set_cookies_admin if c.startswith(f"{ADMIN_ACCESS_COOKIE}="))
    assert "httponly" in adm_access_hdr.lower()
    assert "secure" in adm_access_hdr.lower()
    assert "samesite=strict" in adm_access_hdr.lower()
    assert "domain=" not in adm_access_hdr.lower()

    # Verify vercel.json configures the external Render API reverse proxy while preserving SPA fallback and cache policy
    vercel_text = (REPO_ROOT / "frontend" / "vercel.json").read_text(encoding="utf-8")
    assert "<RENDER_API_HOST>" not in vercel_text
    assert "REPLACE-WITH-YOUR-STAGING-API-HOST" not in vercel_text

    vercel_cfg = json.loads(vercel_text)
    rewrites = vercel_cfg.get("rewrites", [])
    assert len(rewrites) == 2

    api_idx = next(
        i for i, r in enumerate(rewrites)
        if r.get("source") == "/api/:path*"
    )
    spa_idx = next(
        i for i, r in enumerate(rewrites)
        if r.get("destination") == "/index.html"
    )
    assert api_idx < spa_idx
    assert rewrites[api_idx]["destination"] == "https://digi-verse-backend.onrender.com/api/:path*"

    spa_rewrite = rewrites[spa_idx]
    assert spa_rewrite["source"] == "/((?!api/).*)"
    assert spa_rewrite["destination"] == "/index.html"

    for api_path in ("/api/health", "/api/ready", "/api/auth/me", "/api/products", "/api/banners", "/api/uploads/images/sample.png"):
        assert re.fullmatch(spa_rewrite["source"], api_path) is None
    for api_proxy_path in ("/api", "/api/health", "/api/ready", "/api/auth/me", "/api/uploads/images/sample.png"):
        assert re.fullmatch(r"/api(?:/.*)?", api_proxy_path) is not None
    for spa_path in ("/", "/products", "/categories", "/admin/login", "/seller"):
        assert re.fullmatch(spa_rewrite["source"], spa_path) is not None

    headers_rules = vercel_cfg.get("headers", [])
    api_hdr_idx = next(i for i, h in enumerate(headers_rules) if h.get("source") == "/api/(.*)")
    img_hdr_idx = next(i for i, h in enumerate(headers_rules) if h.get("source") == "/api/uploads/images/(.*)")
    assert api_hdr_idx < img_hdr_idx

    for api_path in ("/api/health", "/api/ready", "/api/products", "/api/auth/me"):
        cc = _resolve_vercel_cache_control(headers_rules, api_path)
        assert cc is not None and "no-store" in cc
        assert cc == "no-store, no-cache, must-revalidate"
    assert (
        _resolve_vercel_cache_control(headers_rules, "/api/uploads/images/0123456789abcdef0123456789abcdef.png")
        == "public, max-age=86400"
    )


# ---------------------------------------------------------------------------
# 6. Stage 2.2 Fixes: H1 R2 Credential Isolation, H2 R2 Endpoint Rules,
#    H3 Render Workers, H4 Documented Vercel Cache Header Precedence
# ---------------------------------------------------------------------------


def test_r2_credential_isolation_blocks_implicit_private_key_reuse(monkeypatch):
    # Private asset credentials set, but dedicated image credentials missing:
    # readiness MUST fail and resolve_image_s3_settings must NOT inherit ASSET_STORAGE_* secrets.
    s_no_img_creds = _make_settings(
        **_minimal_prod_kwargs(
            ASSET_STORAGE_BACKEND="s3",
            ASSET_STORAGE_BUCKET="priv-assets-bkt",
            ASSET_STORAGE_REGION="auto",
            ASSET_STORAGE_ENDPOINT_URL="https://priv.r2.cloudflarestorage.com",
            ASSET_STORAGE_ACCESS_KEY="priv_only_ak",
            ASSET_STORAGE_SECRET_KEY="priv_only_sk",
            IMAGE_STORAGE_BACKEND="s3",
            IMAGE_STORAGE_BUCKET="pub-images-bkt",
            IMAGE_STORAGE_ENDPOINT_URL="https://pub.r2.cloudflarestorage.com",
        )
    )
    resolved = s_no_img_creds.resolve_image_s3_settings()
    assert resolved["access_key"] == ""
    assert resolved["secret_key"] == ""
    assert s_no_img_creds.get_image_storage_state() == "misconfigured"

    issues = s_no_img_creds.validate_production_readiness()
    assert any("IMAGE_STORAGE_ACCESS_KEY" in i for i in issues)
    assert any("IMAGE_STORAGE_SECRET_KEY" in i for i in issues)

    # Runtime S3ImageStorageProvider must fail closed rather than reusing ASSET_STORAGE_* creds
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "ASSET_STORAGE_BUCKET", "priv-assets-bkt")
    monkeypatch.setattr(settings, "ASSET_STORAGE_ENDPOINT_URL", "https://priv.r2.cloudflarestorage.com")
    monkeypatch.setattr(settings, "ASSET_STORAGE_ACCESS_KEY", "priv_only_ak")
    monkeypatch.setattr(settings, "ASSET_STORAGE_SECRET_KEY", "priv_only_sk")
    monkeypatch.setattr(settings, "IMAGE_STORAGE_BUCKET", "pub-images-bkt")
    monkeypatch.setattr(settings, "IMAGE_STORAGE_ENDPOINT_URL", "https://pub.r2.cloudflarestorage.com")
    monkeypatch.setattr(settings, "IMAGE_STORAGE_ACCESS_KEY", None)
    monkeypatch.setattr(settings, "IMAGE_STORAGE_SECRET_KEY", None)
    with pytest.raises(HTTPException) as exc_missing_creds:
        S3ImageStorageProvider()
    assert exc_missing_creds.value.status_code == 503


def test_r2_endpoint_validation_and_aws_regional_s3_support():
    # 1. R2 (region='auto') with missing endpoint -> fails for BOTH private asset & public image
    s_r2_missing_ep = _make_settings(
        **_minimal_prod_kwargs(
            ASSET_STORAGE_BACKEND="s3",
            ASSET_STORAGE_BUCKET="priv-bkt",
            ASSET_STORAGE_REGION="auto",
            ASSET_STORAGE_ENDPOINT_URL="",
            ASSET_STORAGE_ACCESS_KEY="priv_ak",
            ASSET_STORAGE_SECRET_KEY="priv_sk",
            IMAGE_STORAGE_BACKEND="s3",
            IMAGE_STORAGE_BUCKET="img-bkt",
            IMAGE_STORAGE_REGION="auto",
            IMAGE_STORAGE_ENDPOINT_URL=None,
            IMAGE_STORAGE_ACCESS_KEY="img_ak",
            IMAGE_STORAGE_SECRET_KEY="img_sk",
        )
    )
    issues_missing = s_r2_missing_ep.validate_production_readiness()
    assert any("ASSET_STORAGE_ENDPOINT_URL" in i and "auto" in i for i in issues_missing)
    assert any("IMAGE_STORAGE_ENDPOINT_URL" in i and "auto" in i for i in issues_missing)
    assert s_r2_missing_ep.get_asset_storage_state() == "misconfigured"
    assert s_r2_missing_ep.get_image_storage_state() == "misconfigured"

    with pytest.raises(S3ClientError):
        S3SigV4Client(
            bucket="priv-bkt",
            region="auto",
            endpoint_url="",
            access_key="ak",
            secret_key="sk",
        )

    # 2. R2 (region='auto') with malformed, non-HTTPS, and localhost endpoints -> rejected
    for bad_ep in (
        "acct.r2.cloudflarestorage.com",
        "http://acct.r2.cloudflarestorage.com",
        "https://",
        "https://bad host.example.com",
        "https://localhost:9000",
    ):
        s_bad = _make_settings(
            **_minimal_prod_kwargs(
                ASSET_STORAGE_BACKEND="s3",
                ASSET_STORAGE_BUCKET="priv-bkt",
                ASSET_STORAGE_REGION="auto",
                ASSET_STORAGE_ENDPOINT_URL=bad_ep,
                ASSET_STORAGE_ACCESS_KEY="priv_ak",
                ASSET_STORAGE_SECRET_KEY="priv_sk",
                IMAGE_STORAGE_BACKEND="s3",
                IMAGE_STORAGE_BUCKET="img-bkt",
                IMAGE_STORAGE_REGION="auto",
                IMAGE_STORAGE_ENDPOINT_URL=bad_ep,
                IMAGE_STORAGE_ACCESS_KEY="img_ak",
                IMAGE_STORAGE_SECRET_KEY="img_sk",
            )
        )
        issues_bad = s_bad.validate_production_readiness()
        assert any("ASSET_STORAGE_ENDPOINT_URL" in i for i in issues_bad), f"Failed to reject {bad_ep}"
        assert any("IMAGE_STORAGE_ENDPOINT_URL" in i for i in issues_bad), f"Failed to reject {bad_ep}"

    with pytest.raises(S3ClientError):
        S3SigV4Client(
            bucket="priv-bkt",
            region="auto",
            endpoint_url="http://acct.r2.cloudflarestorage.com",
            access_key="ak",
            secret_key="sk",
            require_https=True,
        )

    # 3. Valid independent R2 HTTPS endpoints pass cleanly
    s_r2_ok = _make_settings(
        **_minimal_prod_kwargs(
            ASSET_STORAGE_BACKEND="s3",
            ASSET_STORAGE_BUCKET="priv-bkt",
            ASSET_STORAGE_REGION="auto",
            ASSET_STORAGE_ENDPOINT_URL="https://acct-priv.r2.cloudflarestorage.com",
            ASSET_STORAGE_ACCESS_KEY="priv_ak",
            ASSET_STORAGE_SECRET_KEY="priv_sk",
            IMAGE_STORAGE_BACKEND="s3",
            IMAGE_STORAGE_BUCKET="img-bkt",
            IMAGE_STORAGE_REGION="auto",
            IMAGE_STORAGE_ENDPOINT_URL="https://acct-pub.r2.cloudflarestorage.com",
            IMAGE_STORAGE_ACCESS_KEY="img_ak",
            IMAGE_STORAGE_SECRET_KEY="img_sk",
        )
    )
    assert s_r2_ok.validate_production_readiness() == []
    assert s_r2_ok.get_asset_storage_state() == "s3"
    assert s_r2_ok.get_image_storage_state() == "s3"

    # 4. Genuine AWS regional S3 (without custom endpoint) remains supported
    s_aws_regional = _make_settings(
        **_minimal_prod_kwargs(
            ASSET_STORAGE_BACKEND="s3",
            ASSET_STORAGE_BUCKET="priv-aws-bkt",
            ASSET_STORAGE_REGION="ap-south-1",
            ASSET_STORAGE_ENDPOINT_URL="",
            ASSET_STORAGE_ACCESS_KEY="aws_priv_ak",
            ASSET_STORAGE_SECRET_KEY="aws_priv_sk",
            IMAGE_STORAGE_BACKEND="s3",
            IMAGE_STORAGE_BUCKET="img-aws-bkt",
            IMAGE_STORAGE_REGION="us-east-1",
            IMAGE_STORAGE_ENDPOINT_URL="",
            IMAGE_STORAGE_ACCESS_KEY="aws_img_ak",
            IMAGE_STORAGE_SECRET_KEY="aws_img_sk",
        )
    )
    assert s_aws_regional.validate_production_readiness() == []
    aws_client = S3SigV4Client(
        bucket="priv-aws-bkt",
        region="ap-south-1",
        endpoint_url="",
        access_key="aws_priv_ak",
        secret_key="aws_priv_sk",
    )
    aws_url, _ = aws_client.signed_headers(method="GET", key="products/demo/file.zip")
    assert aws_url.startswith("https://priv-aws-bkt.s3.ap-south-1.amazonaws.com/")


def test_render_blueprint_and_documented_vercel_cache_headers():
    render_yaml = (REPO_ROOT / "render.production.yaml").read_text(encoding="utf-8")
    assert "--workers 1" in render_yaml
    assert "--workers 2" not in render_yaml
    for env_key in (
        "ASSET_STORAGE_BUCKET",
        "ASSET_STORAGE_ENDPOINT_URL",
        "ASSET_STORAGE_ACCESS_KEY",
        "ASSET_STORAGE_SECRET_KEY",
        "IMAGE_STORAGE_BUCKET",
        "IMAGE_STORAGE_REGION",
        "IMAGE_STORAGE_ENDPOINT_URL",
        "IMAGE_STORAGE_ACCESS_KEY",
        "IMAGE_STORAGE_SECRET_KEY",
        "IMAGE_STORAGE_PREFIX",
    ):
        assert env_key in render_yaml

    prep_doc = (REPO_ROOT / "docs" / "deployment" / "PRODUCTION_DEPLOYMENT_PREP.md").read_text(encoding="utf-8")
    m = re.search(r"```json\s*(\{.*?\})\s*```", prep_doc, re.DOTALL)
    assert m is not None
    doc_vercel = json.loads(m.group(1))

    assert _resolve_vercel_cache_control(doc_vercel["headers"], "/api/products") == "no-store, no-cache, must-revalidate"
    assert _resolve_vercel_cache_control(doc_vercel["headers"], "/api/auth/me") == "no-store, no-cache, must-revalidate"
    assert (
        _resolve_vercel_cache_control(
            doc_vercel["headers"],
            "/api/uploads/images/0123456789abcdef0123456789abcdef.png",
        )
        == "public, max-age=86400"
    )

    rewrites = doc_vercel["rewrites"]
    assert rewrites[0]["source"] == "/api/:path*"
    assert rewrites[1]["source"] == "/((?!api(?:/|$)).*)"

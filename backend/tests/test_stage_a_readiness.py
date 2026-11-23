"""Stage A Deployment Readiness Unit & Middleware Tests (No production DB or external API calls)."""
from __future__ import annotations

import asyncio
import io
import uuid

import httpx

from app.core.config import Settings, settings
from app.core.database import get_db
from app.main import app


def _valid_production_kwargs() -> dict:
    return {
        "ENVIRONMENT": "production",
        "DEBUG": False,
        "DATABASE_URL": "postgresql+psycopg://app_user:prod_secret_pw_123@db.internal.example:5432/digiverse_prod?sslmode=require",
        "JWT_SECRET_KEY": "c" * 64,
        "ADMIN_JWT_SECRET_KEY": "d" * 64,
        "COOKIE_SECURE": True,
        "TRUST_PROXY_HEADERS": True,
        "RATE_LIMIT_USE_DB": True,
        "CORS_ORIGINS": ["https://store.example.com"],
        "ALLOWED_HOSTS": ["store.example.com", "api.example.com", "testserver"],
        "ASSET_STORAGE_BACKEND": "s3",
        "ASSET_STORAGE_BUCKET": "digiverse-prod-private-assets",
        "ASSET_STORAGE_REGION": "auto",
        "ASSET_STORAGE_ENDPOINT_URL": "https://acct.r2.cloudflarestorage.com",
        "ASSET_STORAGE_ACCESS_KEY": "prod_r2_access_key_value",
        "ASSET_STORAGE_SECRET_KEY": "prod_r2_secret_key_value",
        "IMAGE_STORAGE_BACKEND": "s3",
        "IMAGE_STORAGE_BUCKET": "digiverse-prod-public-images",
        "IMAGE_STORAGE_REGION": "auto",
        "IMAGE_STORAGE_ENDPOINT_URL": "https://acct.r2.cloudflarestorage.com",
        "IMAGE_STORAGE_ACCESS_KEY": "prod_r2_img_access_key_value",
        "IMAGE_STORAGE_SECRET_KEY": "prod_r2_img_secret_key_value",
        "PAYMENT_PROVIDER": "razorpay",
        "RAZORPAY_KEY_ID": "rzp_live_ProdKey123456",
        "RAZORPAY_KEY_SECRET": "prod_razorpay_secret_value",
        "RAZORPAY_WEBHOOK_SECRET": "prod_razorpay_webhook_secret_value",
        "OTP_DELIVERY_PROVIDER": "whatsapp",
        "ENABLE_DEV_OTP": False,
        "WHATSAPP_OTP_ENABLED": True,
        "WHATSAPP_ACCESS_TOKEN": "prod_wa_access_token_value",
        "WHATSAPP_PHONE_NUMBER_ID": "10987654321",
        "WHATSAPP_TEMPLATE_NAME": "verification_code",
        "WHATSAPP_GRAPH_API_VERSION": "v20.0",
        "WHATSAPP_APP_SECRET": "prod_wa_app_secret_value",
        "WHATSAPP_WEBHOOK_VERIFY_TOKEN": "prod_wa_verify_token_value",
        "RESEND_API_KEY": "re_prod_api_key_value",
        "RESEND_FROM_EMAIL": "DIGI-VERSE <noreply@store.example.com>",
        "RESEND_WEBHOOK_SECRET": "whsec_cHJvZF9yZXNlbmRfd2hfc2VjcmV0",
    }


def _make_prod_settings(**overrides) -> Settings:
    data = _valid_production_kwargs()
    data.update(overrides)
    return Settings(_env_file=None, **data)


def test_production_readiness_passes_with_valid_config():
    prod = _make_prod_settings()
    assert prod.is_production is True
    assert prod.validate_production_readiness() == []


def test_non_production_environments_do_not_trigger_production_failures():
    dev = Settings(
        _env_file=None,
        ENVIRONMENT="development",
        DEBUG=True,
        DATABASE_URL="postgresql+psycopg://user:pw@localhost:5432/digiverse",
        JWT_SECRET_KEY="change_me_in_env",
        PAYMENT_PROVIDER="mock",
        OTP_DELIVERY_PROVIDER="development",
        ENABLE_DEV_OTP=True,
    )
    assert dev.validate_production_readiness() == []

    staging = Settings(
        _env_file=None,
        ENVIRONMENT="staging",
        DEBUG=False,
        DATABASE_URL="postgresql+psycopg://user:pw@staging-db.example:5432/digiverse_staging?sslmode=require",
        JWT_SECRET_KEY="a" * 64,
        ADMIN_JWT_SECRET_KEY="b" * 64,
        COOKIE_SECURE=True,
        TRUST_PROXY_HEADERS=True,
        RATE_LIMIT_USE_DB=True,
        CORS_ORIGINS=["https://staging.example.com"],
        ALLOWED_HOSTS=["staging.example.com"],
        ASSET_STORAGE_BACKEND="s3",
        ASSET_STORAGE_BUCKET="staging-bucket",
        ASSET_STORAGE_ACCESS_KEY="staging_ak",
        ASSET_STORAGE_SECRET_KEY="staging_sk",
        PAYMENT_PROVIDER="razorpay",
        RAZORPAY_KEY_ID="rzp_test_staging_key",
        RAZORPAY_KEY_SECRET="staging_secret",
        ENABLE_DEV_OTP=False,
    )
    assert staging.validate_production_readiness() == []
    assert staging.validate_staging_readiness() == []


def test_production_readiness_database_tls_and_no_localhost():
    s_localhost = _make_prod_settings(
        DATABASE_URL="postgresql+psycopg://app_user:prod_secret_pw_123@localhost:5432/digiverse_prod?sslmode=require"
    )
    issues_local = s_localhost.validate_production_readiness()
    assert any("DATABASE_URL" in i and "localhost" in i for i in issues_local)
    assert "prod_secret_pw_123" not in " ".join(issues_local)

    s_loopback = _make_prod_settings(
        DATABASE_URL="postgresql+psycopg://app_user:prod_secret_pw_123@127.0.0.1:5432/digiverse_prod?sslmode=require"
    )
    assert any("DATABASE_URL" in i and "localhost" in i for i in s_loopback.validate_production_readiness())

    s_no_tls = _make_prod_settings(
        DATABASE_URL="postgresql+psycopg://app_user:prod_secret_pw_123@db.internal.example:5432/digiverse_prod"
    )
    issues_tls = s_no_tls.validate_production_readiness()
    assert any("TLS" in i for i in issues_tls)
    assert "prod_secret_pw_123" not in " ".join(issues_tls)


def test_production_readiness_cors_https_and_proxy_headers():
    s_http = _make_prod_settings(CORS_ORIGINS=["http://store.example.com"])
    assert any("CORS_ORIGINS" in i and "HTTPS" in i for i in s_http.validate_production_readiness())

    s_local_cors = _make_prod_settings(CORS_ORIGINS=["https://localhost:5173"])
    assert any("CORS_ORIGINS" in i and "localhost" in i for i in s_local_cors.validate_production_readiness())

    s_empty_cors = _make_prod_settings(CORS_ORIGINS=[])
    assert any("CORS_ORIGINS" in i for i in s_empty_cors.validate_production_readiness())

    s_no_proxy = _make_prod_settings(TRUST_PROXY_HEADERS=False)
    assert any("TRUST_PROXY_HEADERS" in i for i in s_no_proxy.validate_production_readiness())


def test_production_readiness_s3_storage_and_placeholders():
    s_local = _make_prod_settings(ASSET_STORAGE_BACKEND="local")
    assert any("ASSET_STORAGE_BACKEND" in i for i in s_local.validate_production_readiness())

    s_placeholder = _make_prod_settings(
        ASSET_STORAGE_BUCKET="your_private_asset_bucket_name",
        ASSET_STORAGE_ACCESS_KEY="your_s3_access_key_placeholder",
        ASSET_STORAGE_SECRET_KEY="your_s3_secret_key_placeholder",
        ASSET_STORAGE_ENDPOINT_URL="https://your-s3-compatible-endpoint.example.com",
    )
    issues = s_placeholder.validate_production_readiness()
    assert any("ASSET_STORAGE_BUCKET" in i for i in issues)
    assert any("ASSET_STORAGE_ACCESS_KEY" in i for i in issues)
    assert any("ASSET_STORAGE_SECRET_KEY" in i for i in issues)
    assert any("ASSET_STORAGE_ENDPOINT_URL" in i for i in issues)


def test_production_readiness_razorpay_live_credentials_and_webhook_secret():
    s_test_key = _make_prod_settings(RAZORPAY_KEY_ID="rzp_test_123456")
    assert any("RAZORPAY_KEY_ID" in i for i in s_test_key.validate_production_readiness())

    s_missing_sec = _make_prod_settings(
        RAZORPAY_KEY_SECRET="your_razorpay_key_secret_placeholder",
        RAZORPAY_WEBHOOK_SECRET="your_razorpay_webhook_secret_placeholder",
    )
    issues = s_missing_sec.validate_production_readiness()
    assert any("RAZORPAY_KEY_SECRET" in i for i in issues)
    assert any("RAZORPAY_WEBHOOK_SECRET" in i for i in issues)
    assert "prod_razorpay" not in " ".join(issues)


def test_production_readiness_whatsapp_and_resend_consistency():
    s_otp_mismatch = _make_prod_settings(
        OTP_DELIVERY_PROVIDER="development",
        WHATSAPP_OTP_ENABLED=False,
        ENABLE_DEV_OTP=True,
    )
    otp_issues = s_otp_mismatch.validate_production_readiness()
    assert any("ENABLE_DEV_OTP" in i for i in otp_issues)
    assert any("OTP_DELIVERY_PROVIDER" in i for i in otp_issues)
    assert any("WHATSAPP_OTP_ENABLED" in i for i in otp_issues)

    s_wa_partial_webhook = _make_prod_settings(
        WHATSAPP_APP_SECRET="prod_wa_app_secret_value",
        WHATSAPP_WEBHOOK_VERIFY_TOKEN="your_whatsapp_webhook_verify_token_placeholder",
        WHATSAPP_GRAPH_API_VERSION="bad_ver",
    )
    wa_issues = s_wa_partial_webhook.validate_production_readiness()
    assert any("WHATSAPP_WEBHOOK_VERIFY_TOKEN" in i for i in wa_issues)
    assert any("WHATSAPP_GRAPH_API_VERSION" in i for i in wa_issues)
    assert "prod_wa_app_secret_value" not in " ".join(wa_issues)

    s_resend_bad = _make_prod_settings(
        RESEND_API_KEY="your_resend_api_key_placeholder",
        RESEND_FROM_EMAIL="DIGI-VERSE <noreply@digiverse.internal>",
        RESEND_WEBHOOK_SECRET="whsec_your_resend_webhook_secret_placeholder",
    )
    resend_issues = s_resend_bad.validate_production_readiness()
    assert any("RESEND_API_KEY" in i for i in resend_issues)
    assert any("RESEND_FROM_EMAIL" in i for i in resend_issues)
    assert any("RESEND_WEBHOOK_SECRET" in i for i in resend_issues)


def test_seller_and_admin_asset_upload_body_size_limits(monkeypatch):
    def _dummy_db():
        yield None

    monkeypatch.setattr(settings, "MAX_REQUEST_BODY_BYTES", 1024)
    monkeypatch.setattr(settings, "MAX_ASSET_UPLOAD_BYTES", 1024 * 1024)

    async def _exercise_routes() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            pid = uuid.uuid4()
            between_limits = b"x" * 2048  # > MAX_REQUEST_BODY_BYTES (1024), < MAX_ASSET_UPLOAD_BYTES + 2MB
            above_asset_limit = str(settings.MAX_ASSET_UPLOAD_BYTES + (2 * 1024 * 1024) + 1)

            # Seller asset upload > MAX_REQUEST_BODY_BYTES passes size middleware (hits auth 401, not 413)
            r_seller_ok_size = await client.post(
                f"/api/seller/products/{pid}/asset",
                files={"file": ("kit.zip", io.BytesIO(between_limits), "application/zip")},
            )
            assert r_seller_ok_size.status_code == 401

            # Admin asset upload > MAX_REQUEST_BODY_BYTES passes size middleware (hits auth 401, not 413)
            r_admin_ok_size = await client.post(
                f"/api/admin/products/{pid}/asset",
                files={"file": ("kit.zip", io.BytesIO(between_limits), "application/zip")},
            )
            assert r_admin_ok_size.status_code == 401

            # Both seller and admin asset uploads exceeding MAX_ASSET_UPLOAD_BYTES + 2MB return 413
            r_seller_too_big = await client.post(
                f"/api/seller/products/{pid}/asset",
                headers={"Content-Length": above_asset_limit},
            )
            assert r_seller_too_big.status_code == 413

            r_admin_too_big = await client.post(
                f"/api/admin/products/{pid}/asset",
                headers={"Content-Length": above_asset_limit},
            )
            assert r_admin_too_big.status_code == 413

            # Unrelated endpoints remain strictly bounded by MAX_REQUEST_BODY_BYTES
            r_unrelated_login = await client.post(
                "/api/auth/login",
                content=between_limits,
                headers={"Content-Type": "application/json"},
            )
            assert r_unrelated_login.status_code == 413

            r_unrelated_seller_create = await client.post(
                "/api/seller/products",
                content=between_limits,
                headers={"Content-Type": "application/json"},
            )
            assert r_unrelated_seller_create.status_code == 413

    app.dependency_overrides[get_db] = _dummy_db
    try:
        asyncio.run(_exercise_routes())
    finally:
        app.dependency_overrides.pop(get_db, None)

"""Phase 7 Comprehensive Security Audit & Regression Tests.

Covers:
- Authentication & Session Security (cross-role token isolation, CSRF cookie security, shared DB rate limiter)
- Authorization & IDOR (2 customers + 1 admin: orders, invoices, downloads, cart modification, suspended session)
- Payment Gateway & Commerce Security (replays, amount/currency tampering, out-of-order, refunds, production mock block)
- Digital Product & File Storage Security (single-use download tokens, expired tokens, deleted file source, MIME mismatch)
- API Hardening (TrustedHost, request size limit, safe URL validation, readiness, log secret redaction)
- Marketing Background Execution & Failure Handling (failure accuracy, duplicate prevention, unsubscribe)
"""
import io
import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.logging import redact_sensitive_data
from app.core.rate_limit import SharedRateLimiter
from app.core.security import (
    ADMIN_ACCESS_COOKIE,
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    CUSTOMER_ACCESS_COOKIE,
)
from app.main import app
from app.models.enums import AccountStatus, CampaignStatus, DeliveryStatus, OrderStatus
from app.services.admin_auth_service import provision_initial_admin
from app.services.commerce_service import _create_signed_download_token
from app.services.email_service import dev_email_provider
from app.services.operations_service import process_scheduled_campaigns
from app.services.payment_gateway import MockPaymentProvider, get_payment_provider
from app.services.whatsapp_service import dev_whatsapp_provider

VALID_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture(autouse=True)
def _use_mock_payment_provider(monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "mock")
    monkeypatch.setattr(settings, "MAX_DOWNLOADS_PER_ORDER_ITEM", 3)


def _csrf(client) -> dict[str, str]:
    token = client.cookies.get(CSRF_COOKIE_NAME)
    return {CSRF_HEADER_NAME: token} if token else {}


def _register_customer(client, name: str = "Audit Customer", email_consent: bool = True, whatsapp_consent: bool = True):
    suffix = uuid.uuid4().hex[:8]
    res = client.post(
        "/api/auth/register",
        json={
            "full_name": name,
            "email": f"audit-{suffix}@example.test",
            "phone_number": f"+9193{str(uuid.uuid4().int)[:8]}",
            "password": "StrongAuditPass#2026!",
            "email_marketing_consent": email_consent,
            "whatsapp_marketing_consent": whatsapp_consent,
        },
    )
    assert res.status_code == 201
    return _csrf(client), res.json()["customer"], dict(client.cookies)


def _login_admin(client, db):
    init_pw = "AdminInitial#2026!"
    new_pw = "AdminActive#2027!"
    provision_initial_admin(db, initial_password_override=init_pw)
    r = client.post("/api/admin/auth/login", json={"username": "Aayan", "password": init_pw})
    if r.status_code == 401:
        r = client.post("/api/admin/auth/login", json={"username": "Aayan", "password": new_pw})
    assert r.status_code == 200
    if r.json()["must_change_password"]:
        r2 = client.post(
            "/api/admin/auth/change-password",
            json={"current_password": init_pw, "new_password": new_pw},
            headers=_csrf(client),
        )
        assert r2.status_code == 200
    return _csrf(client), dict(client.cookies)


# ===========================================================================
# 1. AUTHENTICATION, ROLE ISOLATION & SHARED POSTGRES RATE LIMITER
# ===========================================================================


def test_admin_token_cannot_impersonate_customer_and_csrf_cookie_flags(api_client, db, monkeypatch):
    monkeypatch.setattr(settings, "COOKIE_SECURE", True)
    csrf_res = api_client.get("/api/auth/csrf")
    assert csrf_res.status_code == 200
    set_cookie_hdr = csrf_res.headers.get("set-cookie", "").lower()
    assert "secure" in set_cookie_hdr
    assert "samesite=lax" in set_cookie_hdr
    monkeypatch.setattr(settings, "COOKIE_SECURE", False)

    api_client.cookies.clear()
    _, admin_cookies = _login_admin(api_client, db)
    admin_access = admin_cookies[ADMIN_ACCESS_COOKIE]

    # Admin cookie alone must not authenticate customer endpoints
    assert api_client.get("/api/auth/me").status_code == 401
    assert api_client.get("/api/orders").status_code == 401

    # Passing Admin JWT as Bearer on customer endpoint must also be rejected
    bearer_res = api_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {admin_access}"},
    )
    assert bearer_res.status_code == 401


def test_shared_postgres_rate_limiter_enforces_across_workers(engine):
    # Two independent SharedRateLimiter instances simulate two separate backend worker processes
    worker_a = SharedRateLimiter()
    worker_b = SharedRateLimiter()
    worker_a.reset(engine=engine)
    bucket = f"audit_shared_{uuid.uuid4().hex[:8]}"
    identifier = "198.51.100.42"

    try:
        worker_a._check_postgres(engine, f"{bucket}:{identifier}", max_requests=3, window_seconds=60)
        worker_b._check_postgres(engine, f"{bucket}:{identifier}", max_requests=3, window_seconds=60)
        worker_a._check_postgres(engine, f"{bucket}:{identifier}", max_requests=3, window_seconds=60)

        with pytest.raises(HTTPException) as exc_info:
            worker_b._check_postgres(engine, f"{bucket}:{identifier}", max_requests=3, window_seconds=60)
        assert exc_info.value.status_code == 429
    finally:
        worker_a.reset(engine=engine)


# ===========================================================================
# 2. AUTHORIZATION, IDOR & SUSPENDED SESSION ENFORCEMENT
# ===========================================================================


def test_idor_and_authorization_two_customers_and_admin(api_client, db, make_category, make_product):
    import hashlib
    import zipfile
    from app.services.asset_storage_service import get_asset_storage

    cat = make_category(name="IDOR Cat", slug="idor-cat", is_active=True)
    prod = make_product(
        category=cat,
        name="IDOR Asset",
        slug="idor-asset",
        original_price=Decimal("400.00"),
        is_active=True,
    )
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w") as zf:
        zf.writestr("idor.txt", "idor asset")
    zbytes = zbuf.getvalue()
    skey = f"products/{prod.id}/{uuid.uuid4().hex}.zip"
    get_asset_storage("local").save(
        io.BytesIO(zbytes),
        storage_key=skey,
        content_type="application/zip",
        size_bytes=len(zbytes),
        sha256_hex=hashlib.sha256(zbytes).hexdigest(),
    )
    prod.asset_storage_backend = "local"
    prod.asset_storage_key = skey
    prod.asset_original_filename = "idor-asset.zip"
    prod.asset_content_type = "application/zip"
    prod.asset_size_bytes = len(zbytes)
    prod.private_download_url = "asset://managed"
    db.flush()

    # Customer A adds item to cart, checks out, verifies payment, and generates a download grant
    headers_a, cust_a, cookies_a = _register_customer(api_client, "Customer Alpha")
    cart_a = api_client.post(
        "/api/cart/items",
        json={"product_id": str(prod.id), "quantity": 1},
        headers=headers_a,
    ).json()
    cart_item_a_id = cart_a["items"][0]["id"]

    # Customer B cannot update or delete Customer A's cart item
    api_client.cookies.clear()
    headers_b, cust_b, cookies_b = _register_customer(api_client, "Customer Beta")
    assert (
        api_client.patch(
            f"/api/cart/items/{cart_item_a_id}",
            json={"quantity": 5},
            headers=headers_b,
        ).status_code
        == 404
    )
    assert api_client.delete(f"/api/cart/items/{cart_item_a_id}", headers=headers_b).status_code == 404

    # Switch back to Customer A, checkout & pay
    api_client.cookies.clear()
    for k, v in cookies_a.items():
        api_client.cookies.set(k, v)
    chk = api_client.post("/api/checkout", headers=headers_a).json()
    order_a_id = chk["order_id"]
    gw_order_id = chk["payment"]["gateway_order_id"]
    gw_pay_id = f"pay_idor_{uuid.uuid4().hex[:8]}"
    ver = api_client.post(
        "/api/payments/verify",
        json={
            "order_id": order_a_id,
            "gateway_order_id": gw_order_id,
            "gateway_payment_id": gw_pay_id,
            "gateway_signature": MockPaymentProvider.sign_payment(gw_order_id, gw_pay_id),
        },
        headers=headers_a,
    ).json()
    order_item_a_id = ver["items"][0]["id"]
    dl_grant = api_client.post(f"/api/downloads/{order_item_a_id}", headers=headers_a).json()

    # Customer B cannot access Customer A's order, invoice, retry-payment, download grant, status, or file
    api_client.cookies.clear()
    for k, v in cookies_b.items():
        api_client.cookies.set(k, v)
    assert api_client.get(f"/api/orders/{order_a_id}").status_code == 403
    assert api_client.get(f"/api/orders/{order_a_id}/invoice").status_code == 403
    assert api_client.post(f"/api/orders/{order_a_id}/retry-payment", headers=headers_b).status_code == 403
    assert api_client.post(f"/api/downloads/{order_item_a_id}", headers=headers_b).status_code == 403
    assert api_client.get(f"/api/downloads/{dl_grant['download_id']}/status").status_code == 403
    assert api_client.get(dl_grant["download_url"]).status_code == 403

    # Customers cannot access admin endpoints
    assert api_client.get("/api/admin/orders").status_code == 403
    assert api_client.get("/api/admin/customers").status_code == 403
    assert (
        api_client.patch(
            f"/api/admin/orders/{order_a_id}/status",
            json={"status": "refunded"},
            headers=headers_b,
        ).status_code
        == 403
    )

    # Admin suspends Customer A -> Customer A's existing session is immediately revoked
    api_client.cookies.clear()
    admin_headers, _ = _login_admin(api_client, db)
    susp_res = api_client.patch(
        f"/api/admin/customers/{cust_a['id']}/status",
        json={"account_status": AccountStatus.SUSPENDED.value},
        headers=admin_headers,
    )
    assert susp_res.status_code == 200

    api_client.cookies.clear()
    for k, v in cookies_a.items():
        api_client.cookies.set(k, v)
    assert api_client.get("/api/auth/me").status_code in (401, 403)
    assert api_client.get("/api/orders").status_code in (401, 403)


# ===========================================================================
# 3. PAYMENT SECURITY & DOWNLOAD TOKEN LIFECYCLE
# ===========================================================================


def test_payment_amount_currency_mismatch_duplicate_refund_and_production_mock_guard(
    api_client, db, make_category, make_product, monkeypatch
):
    # Mock provider must be strictly blocked in production
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    with pytest.raises(HTTPException) as exc_info:
        get_payment_provider()
    assert exc_info.value.status_code == 503
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    cat = make_category(name="Pay Audit", slug="pay-audit", is_active=True)
    prod = make_product(
        category=cat,
        name="Pay Audit Asset",
        slug="pay-audit-asset",
        original_price=Decimal("750.00"),
        is_active=True,
        private_download_url="https://storage.example.test/private/pay-audit.zip",
    )

    headers, _, _ = _register_customer(api_client, "Payment Audit Buyer")
    api_client.post("/api/cart/items", json={"product_id": str(prod.id), "quantity": 1}, headers=headers)
    chk = api_client.post("/api/checkout", headers=headers).json()
    order_id = chk["order_id"]
    gw_order_id = chk["payment"]["gateway_order_id"]
    gw_pay_id = f"pay_aud_{uuid.uuid4().hex[:8]}"

    # 1. Webhook with wrong amount rejected (400)
    bad_amt_wh = json.dumps({
        "event_id": f"evt_badamt_{uuid.uuid4().hex[:8]}",
        "event": "payment.captured",
        "payload": {"payment": {"entity": {"id": gw_pay_id, "order_id": gw_order_id, "amount": 100, "currency": "INR"}}},
    }).encode("utf-8")
    assert (
        api_client.post(
            "/api/payments/webhook",
            content=bad_amt_wh,
            headers={"Content-Type": "application/json", "X-Razorpay-Signature": MockPaymentProvider.sign_webhook(bad_amt_wh)},
        ).status_code
        == 400
    )

    # 2. Webhook with wrong currency rejected (400)
    bad_cur_wh = json.dumps({
        "event_id": f"evt_badcur_{uuid.uuid4().hex[:8]}",
        "event": "payment.captured",
        "payload": {"payment": {"entity": {"id": gw_pay_id, "order_id": gw_order_id, "amount": 75000, "currency": "USD"}}},
    }).encode("utf-8")
    assert (
        api_client.post(
            "/api/payments/webhook",
            content=bad_cur_wh,
            headers={"Content-Type": "application/json", "X-Razorpay-Signature": MockPaymentProvider.sign_webhook(bad_cur_wh)},
        ).status_code
        == 400
    )

    # 3. Payment failure followed by valid verification succeeds
    r_bad_sig = api_client.post(
        "/api/payments/verify",
        json={
            "order_id": order_id,
            "gateway_order_id": gw_order_id,
            "gateway_payment_id": gw_pay_id,
            "gateway_signature": "bad_sig_00000000",
        },
        headers=headers,
    )
    assert r_bad_sig.status_code == 400
    r_ok_sig = api_client.post(
        "/api/payments/verify",
        json={
            "order_id": order_id,
            "gateway_order_id": gw_order_id,
            "gateway_payment_id": gw_pay_id,
            "gateway_signature": MockPaymentProvider.sign_payment(gw_order_id, gw_pay_id),
        },
        headers=headers,
    )
    assert r_ok_sig.status_code == 200
    assert r_ok_sig.json()["payment_status"] == "paid"

    # 4. Refund event arriving more than once is idempotent
    for i in range(2):
        ref_wh = json.dumps({
            "event_id": f"evt_ref_{i}_{uuid.uuid4().hex[:6]}",
            "event": "refund.processed",
            "payload": {
                "payment": {"entity": {"id": gw_pay_id, "order_id": gw_order_id, "amount": 75000, "currency": "INR"}},
                "refund": {"entity": {"id": f"rfnd_{uuid.uuid4().hex[:8]}", "payment_id": gw_pay_id}},
            },
        }).encode("utf-8")
        r_ref = api_client.post(
            "/api/payments/webhook",
            content=ref_wh,
            headers={"Content-Type": "application/json", "X-Razorpay-Signature": MockPaymentProvider.sign_webhook(ref_wh)},
        )
        assert r_ref.status_code == 200
        expected = "refunded" if i == 0 else "already_refunded"
        assert r_ref.json()["status"] == expected


def test_single_use_and_expired_download_tokens_and_deleted_file_guard(
    api_client, db, make_category, make_product
):
    import hashlib
    import zipfile
    from app.services.asset_storage_service import get_asset_storage

    cat = make_category(name="DL Security", slug="dl-security", is_active=True)
    prod = make_product(
        category=cat,
        name="DL Token Asset",
        slug="dl-token-asset",
        original_price=Decimal("350.00"),
        is_active=True,
    )
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr("token-test.txt", "single use asset payload")
    raw_asset = zip_buf.getvalue()
    storage_key = f"products/{prod.id}/{uuid.uuid4().hex}.zip"
    get_asset_storage("local").save(
        io.BytesIO(raw_asset),
        storage_key=storage_key,
        content_type="application/zip",
        size_bytes=len(raw_asset),
        sha256_hex=hashlib.sha256(raw_asset).hexdigest(),
    )
    prod.asset_storage_backend = "local"
    prod.asset_storage_key = storage_key
    prod.asset_original_filename = "dl-token.zip"
    prod.asset_content_type = "application/zip"
    prod.asset_size_bytes = len(raw_asset)
    prod.private_download_url = "asset://managed"
    db.flush()

    headers, cust, _ = _register_customer(api_client, "DL Token Buyer")
    api_client.post("/api/cart/items", json={"product_id": str(prod.id), "quantity": 1}, headers=headers)
    chk = api_client.post("/api/checkout", headers=headers).json()
    order_id = chk["order_id"]
    gw_order_id = chk["payment"]["gateway_order_id"]
    gw_pay_id = f"pay_dl_{uuid.uuid4().hex[:8]}"
    ver = api_client.post(
        "/api/payments/verify",
        json={
            "order_id": order_id,
            "gateway_order_id": gw_order_id,
            "gateway_payment_id": gw_pay_id,
            "gateway_signature": MockPaymentProvider.sign_payment(gw_order_id, gw_pay_id),
        },
        headers=headers,
    ).json()
    order_item_id = ver["items"][0]["id"]

    # 1. Single-use signed token: first GET succeeds with exact binary payload, second GET rejected (403)
    grant = api_client.post(f"/api/downloads/{order_item_id}", headers=headers).json()
    first_dl = api_client.get(grant["download_url"])
    assert first_dl.status_code == 200
    assert first_dl.content == raw_asset
    reuse_resp = api_client.get(grant["download_url"])
    assert reuse_resp.status_code == 403
    assert "already been used" in reuse_resp.json()["detail"].lower()

    # 2. Expired signed download token rejected (403)
    grant2 = api_client.post(f"/api/downloads/{order_item_id}", headers=headers).json()
    from jose import jwt as jose_jwt
    expired_token = jose_jwt.encode(
        {
            "iss": "digiverse",
            "aud": "digiverse:download",
            "sub": cust["id"],
            "did": grant2["download_id"],
            "oiid": order_item_id,
            "type": "signed_download",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=2),
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    assert (
        api_client.get(f"/api/downloads/{grant2['download_id']}/file?token={expired_token}").status_code
        == 403
    )

    # 3. Deleted/missing private_download_url rejected at stream time (404)
    prod.private_download_url = None
    db.flush()
    assert api_client.get(grant2["download_url"]).status_code == 404


# ===========================================================================
# 4. API HARDENING, MIME MISMATCH, SAFE URLS, READINESS & LOG REDACTION
# ===========================================================================


def test_api_hardening_mime_mismatch_safe_urls_readiness_and_log_redaction(
    api_client, db, make_category, make_product
):
    admin_headers, _ = _login_admin(api_client, db)
    cat = make_category(name="Hardening Cat", slug="hardening-cat", is_active=True)
    prod = make_product(category=cat, name="Hardening Prod", slug="hardening-prod")

    # Mismatched Content-Type (PNG bytes declared as image/jpeg) -> 400
    r_mismatch = api_client.post(
        f"/api/admin/products/{prod.id}/images",
        files={"file": ("spoof.png", io.BytesIO(VALID_PNG_BYTES), "image/jpeg")},
        headers=admin_headers,
    )
    assert r_mismatch.status_code == 400

    # Unsafe javascript: URL in banner/category rejected -> 422
    r_xss_banner = api_client.post(
        "/api/admin/banners",
        json={
            "heading": "XSS Test",
            "image_url": "https://cdn.example.test/img.png",
            "cta_destination": "javascript:alert(1)",
        },
        headers=admin_headers,
    )
    assert r_xss_banner.status_code == 422

    # Security & correlation headers present
    r_ready = api_client.get("/api/ready")
    assert r_ready.status_code == 200
    assert r_ready.json()["status"] == "ready"
    assert r_ready.headers.get("X-Request-ID")
    assert r_ready.headers.get("X-Content-Type-Options") == "nosniff"
    assert r_ready.headers.get("X-Frame-Options") == "DENY"
    assert r_ready.headers.get("Permissions-Policy")

    # TrustedHostMiddleware blocks spoofed Host header
    r_host = api_client.get("/api/health", headers={"Host": "evil.attacker.example"})
    assert r_host.status_code == 400

    # Oversized Content-Length rejected -> 413
    r_big = api_client.post(
        "/api/auth/login",
        json={"email": "a@example.test", "password": "x"},
        headers={"Content-Length": str(settings.MAX_REQUEST_BODY_BYTES + 1)},
    )
    assert r_big.status_code == 413

    # Log redaction never leaks sensitive fields
    redacted = redact_sensitive_data(
        {
            "password": "secret-pw",
            "otp_code": "123456",
            "refresh_token": "jwt.token.here",
            "private_download_url": "https://secret.bucket/file.zip",
            "order_number": "DV-123",
        }
    )
    assert redacted["password"] == "[REDACTED]"
    assert redacted["otp_code"] == "[REDACTED]"
    assert redacted["refresh_token"] == "[REDACTED]"
    assert redacted["private_download_url"] == "[REDACTED]"
    assert redacted["order_number"] == "DV-123"


# ===========================================================================
# 5. MARKETING FAILURE TRACKING, SCHEDULER & UNSUBSCRIBE
# ===========================================================================


def test_marketing_failure_handling_scheduler_and_unsubscribe(api_client, db):
    dev_email_provider.clear()
    dev_whatsapp_provider.clear()

    headers_c1, cust1, _ = _register_customer(api_client, "Subscriber One", True, True)
    api_client.cookies.clear()
    _, cust2, _ = _register_customer(api_client, "Subscriber Two", True, True)

    # Customer 1 unsubscribes from email marketing
    api_client.cookies.clear()
    r_c1 = api_client.post(
        "/api/auth/login",
        json={"email": cust1["email"], "password": "StrongAuditPass#2026!"},
    )
    assert r_c1.status_code == 200
    r_unsub = api_client.post("/api/auth/unsubscribe?channel=email", headers=_csrf(api_client))
    assert r_unsub.status_code == 200
    assert r_unsub.json()["email_marketing_consent"] is False

    api_client.cookies.clear()
    admin_headers, _ = _login_admin(api_client, db)

    # Create email campaign & simulate provider failure for Subscriber Two
    camp = api_client.post(
        "/api/admin/campaigns/email",
        json={
            "name": "Failure Tracking Blast",
            "subject": "Test Subject",
            "content": "Test Content",
        },
        headers=admin_headers,
    ).json()

    dev_email_provider.simulate_failure_for.add(cust2["email"])
    r_fail_launch = api_client.post(
        f"/api/admin/campaigns/email/{camp['id']}/launch",
        headers=admin_headers,
    )
    assert r_fail_launch.status_code == 200
    fail_body = r_fail_launch.json()
    assert fail_body["status"] == CampaignStatus.FAILED.value
    assert fail_body["sent_count"] == 0
    assert fail_body["failed_count"] == 1
    # Unsubscribed Customer 1 was NOT targeted
    assert fail_body["targeted_recipients"] == 1

    # Clear failure, schedule campaign, and execute via worker processor
    dev_email_provider.simulate_failure_for.clear()
    r_sched = api_client.post(
        f"/api/admin/campaigns/email/{camp['id']}/schedule",
        headers=admin_headers,
    )
    assert r_sched.status_code == 200
    assert r_sched.json()["status"] == CampaignStatus.SCHEDULED.value

    worker_res = process_scheduled_campaigns(db)
    assert worker_res["email_campaigns"] == 1
    sent_emails = [n["email"] for n in dev_email_provider.sent_notifications]
    assert cust2["email"] in sent_emails
    assert cust1["email"] not in sent_emails

    # WhatsApp failure does not falsely mark campaign completed
    wa_camp = api_client.post(
        "/api/admin/campaigns/whatsapp",
        json={
            "name": "WA Failure Check",
            "content": "Flash offer!",
            "approved_template_name": "digiverse_flash_v1",
        },
        headers=admin_headers,
    ).json()
    dev_whatsapp_provider.simulate_failure_for.add("*")
    r_wa_fail = api_client.post(
        f"/api/admin/campaigns/whatsapp/{wa_camp['id']}/launch",
        headers=admin_headers,
    )
    assert r_wa_fail.status_code == 200
    assert r_wa_fail.json()["status"] == CampaignStatus.FAILED.value
    assert r_wa_fail.json()["sent_count"] == 0
    assert r_wa_fail.json()["failed_count"] == 2


def test_production_rate_limiter_fails_closed_and_failed_checkout_idem_key_retries(
    api_client, db, make_category, make_product, monkeypatch
):
    # 1. Production rate limiter must NEVER silently degrade to in-memory fallback
    limiter = SharedRateLimiter()
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "RATE_LIMIT_USE_DB", True)
    with pytest.raises(HTTPException) as exc_info:
        limiter.check("login", "198.51.100.1", max_requests=5, window_seconds=60, db=db)
    assert exc_info.value.status_code == 503
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    # 2. Checkout with same idempotency_key after a failed payment attempt reuses the same order safely
    cat = make_category(name="Idem Retry", slug="idem-retry", is_active=True)
    prod = make_product(
        category=cat,
        name="Idem Retry Asset",
        slug="idem-retry-asset",
        original_price=Decimal("250.00"),
        is_active=True,
        private_download_url="https://storage.example.test/private/idem-retry.zip",
    )
    headers, _, _ = _register_customer(api_client, "Idem Retry Buyer")
    api_client.post("/api/cart/items", json={"product_id": str(prod.id), "quantity": 1}, headers=headers)
    idem_key = f"retry-idem-{uuid.uuid4().hex[:8]}"
    chk1 = api_client.post("/api/checkout", json={"idempotency_key": idem_key}, headers=headers)
    assert chk1.status_code == 201
    order_id = chk1.json()["order_id"]
    gw_order_id = chk1.json()["payment"]["gateway_order_id"]

    # Fail the first payment attempt
    r_fail = api_client.post(
        "/api/payments/verify",
        json={
            "order_id": order_id,
            "gateway_order_id": gw_order_id,
            "gateway_payment_id": f"pay_fail_{uuid.uuid4().hex[:8]}",
            "gateway_signature": "bad_sig_00000000",
        },
        headers=headers,
    )
    assert r_fail.status_code == 400

    # Re-calling /checkout with the same idempotency_key must NOT crash with IntegrityError
    chk2 = api_client.post("/api/checkout", json={"idempotency_key": idem_key}, headers=headers)
    assert chk2.status_code == 201
    assert chk2.json()["order_id"] == order_id
    assert chk2.json()["payment"]["gateway_order_id"] != gw_order_id


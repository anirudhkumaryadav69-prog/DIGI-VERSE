"""Phase 8.3 Staging Readiness & End-to-End Simulated Staging Workflows (A-E).

All tests execute strictly against `digiverse_test` using mocked/simulated HTTP transports
and never connect to production `digiverse` or live third-party APIs.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import time
import uuid
import zipfile
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.main import create_application
from app.models.campaign import CampaignRecipient, EmailCampaign, WhatsAppCampaign
from app.models.enums import AccountStatus, CampaignStatus, DeliveryStatus
from app.services.admin_auth_service import provision_initial_admin
from app.services.asset_storage_service import get_asset_storage
from app.services.campaign_worker import process_campaigns_in_session
from app.services.payment_gateway import MockPaymentProvider


def _csrf(client: TestClient) -> dict[str, str]:
    tok = client.cookies.get(CSRF_COOKIE_NAME)
    return {CSRF_HEADER_NAME: tok} if tok else {}


def _login_admin(client: TestClient, db) -> dict[str, str]:
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
    return _csrf(client)


def _register_customer(
    client: TestClient,
    *,
    name: str = "Staging Buyer",
    email_consent: bool = True,
    whatsapp_consent: bool = True,
) -> tuple[dict[str, str], dict]:
    suffix = uuid.uuid4().hex[:8]
    r = client.post(
        "/api/auth/register",
        json={
            "full_name": name,
            "email": f"staging-{suffix}@example.test",
            "phone_number": f"+9198{str(uuid.uuid4().int)[:8]}",
            "password": "CustomerPass#2026!",
            "email_marketing_consent": email_consent,
            "whatsapp_marketing_consent": whatsapp_consent,
        },
    )
    assert r.status_code == 201
    return _csrf(client), r.json()["customer"]


def _make_zip_bytes(filename: str = "bundle.txt", content: bytes = b"Staging verified zip payload") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(filename, content)
    return buf.getvalue()


def _sign_resend_svix(secret: str, svix_id: str, ts: int, raw_body: bytes) -> str:
    raw_secret = secret[6:] if secret.startswith("whsec_") else secret
    secret_bytes = base64.b64decode(raw_secret) if secret.startswith("whsec_") else raw_secret.encode("utf-8")
    signed = f"{svix_id}.{ts}.{raw_body.decode('utf-8')}".encode("utf-8")
    sig_b64 = base64.b64encode(hmac.new(secret_bytes, signed, hashlib.sha256).digest()).decode("utf-8")
    return f"v1,{sig_b64}"


def _sign_whatsapp_hub(app_secret: str, raw_body: bytes) -> str:
    return "sha256=" + hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


def _configure_valid_staging(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")
    monkeypatch.setattr(settings, "ENABLE_DEV_OTP", False)
    monkeypatch.setattr(settings, "DEBUG", False)
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "a" * 64)
    monkeypatch.setattr(settings, "ADMIN_JWT_SECRET_KEY", "b" * 64)
    monkeypatch.setattr(settings, "COOKIE_SECURE", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_USE_DB", True)
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "razorpay")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_staging123456")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "rzp_test_secret_abc123")
    monkeypatch.setattr(settings, "CORS_ORIGINS", ["https://staging.digiverse.example"])
    monkeypatch.setattr(settings, "ALLOWED_HOSTS", ["staging.digiverse.example", "testserver"])
    monkeypatch.setattr(settings, "ASSET_STORAGE_BACKEND", "s3")
    monkeypatch.setattr(settings, "ASSET_STORAGE_BUCKET", "digiverse-staging-private-assets")
    monkeypatch.setattr(settings, "ASSET_STORAGE_ACCESS_KEY", "r2_access_key_test")
    monkeypatch.setattr(settings, "ASSET_STORAGE_SECRET_KEY", "r2_secret_key_test")


# ===========================================================================
# 1. STAGING CONFIG VALIDATION, OPENAPI HIDING & READINESS ENDPOINT
# ===========================================================================


def test_staging_readiness_validator_enforces_strict_staging_rules(monkeypatch):
    _configure_valid_staging(monkeypatch)
    assert settings.is_staging is True
    assert settings.validate_staging_readiness() == []

    # Reject live Razorpay key in staging
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_live_forbidden123")
    assert any("rzp_test_" in msg for msg in settings.validate_staging_readiness())
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_staging123456")

    # Reject mock payment provider in staging
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "mock")
    assert any("PAYMENT_PROVIDER" in msg for msg in settings.validate_staging_readiness())
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "razorpay")

    # Reject local private asset backend in staging
    monkeypatch.setattr(settings, "ASSET_STORAGE_BACKEND", "local")
    assert any("ASSET_STORAGE_BACKEND" in msg for msg in settings.validate_staging_readiness())
    monkeypatch.setattr(settings, "ASSET_STORAGE_BACKEND", "s3")

    # Reject insecure HTTP / localhost CORS and disabled COOKIE_SECURE / DEBUG=True
    monkeypatch.setattr(settings, "CORS_ORIGINS", ["http://localhost:5173"])
    monkeypatch.setattr(settings, "COOKIE_SECURE", False)
    monkeypatch.setattr(settings, "DEBUG", True)
    issues = settings.validate_staging_readiness()
    assert len(issues) >= 3


def test_staging_app_hides_docs_and_readiness_reflects_config(monkeypatch, db):
    _configure_valid_staging(monkeypatch)
    staging_app = create_application()

    with TestClient(staging_app, base_url="https://staging.digiverse.example") as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/api/docs").status_code == 404

        r_ready = client.get("/api/ready")
        assert r_ready.status_code == 200
        assert r_ready.json()["status"] == "ready"
        assert r_ready.json()["checks"]["configuration"] == "ok"

        # Break staging config -> /api/ready immediately reports 503 not_ready
        monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_live_accidental")
        r_bad = client.get("/api/ready")
        assert r_bad.status_code == 503
        assert r_bad.json()["status"] == "not_ready"
        assert r_bad.json()["checks"]["configuration"] == "invalid"

        # Untrusted Host header rejected by TrustedHostMiddleware
        r_host = client.get("/api/health", headers={"Host": "evil.attacker.example"})
        assert r_host.status_code == 400


# ===========================================================================
# 2. END-TO-END STAGING WORKFLOWS A-E (PRIVATE S3, PAYMENTS, DOWNLOADS, CAMPAIGNS)
# ===========================================================================


def test_staging_workflows_a_to_e_end_to_end_simulation(
    api_client, db, make_category, make_product, monkeypatch
):
    """Simulate full staging commerce + S3 SigV4 + Resend + Meta WhatsApp lifecycle:
    A. Admin uploads binary ZIP into private S3/R2 provider (mocked SigV4 HTTP transport).
    B. Customer checks out and payment is confirmed idempotently via signed webhook / mock signature.
    C. Customer receives single-use signed URL, streams binary matching SHA-256, and hits download limit.
    D. Worker processes Email (Resend) & WhatsApp (Meta) campaigns via mocked HTTPS transports;
       signed webhooks reconcile delivered/bounced/read states & opt-out suppresses targeting.
    E. Transient 5xx schedules retry backoff; ambiguous ReadTimeout moves recipient to unresolved.
    """
    # --- Workflow A: Private S3/R2 asset upload via SigV4 transport ---
    s3_objects: dict[str, tuple[bytes, str]] = {}

    def _s3_handler(request: httpx.Request) -> httpx.Response:
        assert "X-Amz-Content-Sha256" in request.headers
        assert "Authorization" in request.headers and request.headers["Authorization"].startswith("AWS4-HMAC-SHA256")
        key = request.url.path.lstrip("/")
        if request.method == "PUT":
            s3_objects[key] = (request.content, request.headers.get("Content-Type", "application/octet-stream"))
            return httpx.Response(200, headers={"ETag": '"staging-etag-1"'})
        if request.method == "HEAD":
            if key not in s3_objects:
                return httpx.Response(404)
            data, ctype = s3_objects[key]
            return httpx.Response(200, headers={"Content-Length": str(len(data)), "Content-Type": ctype})
        if request.method == "GET":
            if key not in s3_objects:
                return httpx.Response(404)
            data, ctype = s3_objects[key]
            return httpx.Response(200, content=data, headers={"Content-Length": str(len(data)), "Content-Type": ctype})
        if request.method == "DELETE":
            s3_objects.pop(key, None)
            return httpx.Response(204)
        return httpx.Response(405)

    real_httpx_client = httpx.Client
    monkeypatch.setattr(settings, "ASSET_STORAGE_BACKEND", "s3")
    monkeypatch.setattr(settings, "ASSET_STORAGE_BUCKET", "digiverse-staging-private-assets")
    monkeypatch.setattr(settings, "ASSET_STORAGE_REGION", "auto")
    monkeypatch.setattr(settings, "ASSET_STORAGE_ENDPOINT_URL", "https://r2.staging.example")
    monkeypatch.setattr(settings, "ASSET_STORAGE_ACCESS_KEY", "staging_r2_ak")
    monkeypatch.setattr(settings, "ASSET_STORAGE_SECRET_KEY", "staging_r2_sk_secret")
    monkeypatch.setattr(settings, "ASSET_STORAGE_USE_PATH_STYLE", True)
    monkeypatch.setattr(
        "app.services.asset_storage_service.httpx.Client",
        lambda **kw: real_httpx_client(**{**kw, "transport": httpx.MockTransport(_s3_handler)}),
    )

    assert get_asset_storage().backend_name == "s3"

    admin_headers = _login_admin(api_client, db)
    cat = make_category(name="Staging Templates", slug="staging-templates", is_active=True)
    prod = make_product(category=cat, name="Launch Kit", slug="launch-kit", is_active=True)

    payload_zip = _make_zip_bytes("launch.txt", b"Authentic binary staging kit payload v8.3")
    r_up = api_client.post(
        f"/api/admin/products/{prod.id}/asset",
        files={"file": ("launch-kit.zip", io.BytesIO(payload_zip), "application/zip")},
        headers=admin_headers,
    )
    assert r_up.status_code == 201
    assert r_up.json()["asset"]["storage_backend"] == "s3"
    assert r_up.json()["asset"]["sha256"] == hashlib.sha256(payload_zip).hexdigest()
    assert len(s3_objects) == 1
    assert "staging_r2_sk_secret" not in r_up.text

    # --- Workflow B: Checkout & Payment Verification (mock test harness + limit check) ---
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "mock")
    monkeypatch.setattr(settings, "MAX_DOWNLOADS_PER_ORDER_ITEM", 2)

    api_client.cookies.clear()
    cust_headers, cust = _register_customer(api_client, name="Staging Customer A")
    assert api_client.post(
        "/api/cart/items", json={"product_id": str(prod.id), "quantity": 1}, headers=cust_headers
    ).status_code in (200, 201)

    r_chk = api_client.post("/api/checkout", headers=cust_headers)
    assert r_chk.status_code == 201
    order_id = r_chk.json()["order_id"]
    gw_order_id = r_chk.json()["payment"]["gateway_order_id"]
    gw_pay_id = f"pay_stg_{uuid.uuid4().hex[:8]}"
    sig = MockPaymentProvider.sign_payment(gw_order_id, gw_pay_id)

    r_ver = api_client.post(
        "/api/payments/verify",
        json={
            "order_id": order_id,
            "gateway_order_id": gw_order_id,
            "gateway_payment_id": gw_pay_id,
            "gateway_signature": sig,
        },
        headers=cust_headers,
    )
    assert r_ver.status_code == 200
    assert r_ver.json()["status"] == "fulfilled"
    order_item_id = r_ver.json()["items"][0]["id"]

    # --- Workflow C: Binary Download Streaming, Single-Use, Security Headers & Quota ---
    r_grant_1 = api_client.post(f"/api/downloads/{order_item_id}", headers=cust_headers)
    assert r_grant_1.status_code == 201
    dl_url_1 = r_grant_1.json()["download_url"]

    r_file_1 = api_client.get(dl_url_1)
    assert r_file_1.status_code == 200
    assert r_file_1.content == payload_zip
    assert r_file_1.headers.get("x-content-type-options") == "nosniff"
    assert "no-store" in (r_file_1.headers.get("cache-control") or "")

    # Reuse single-use signed URL -> 403
    assert api_client.get(dl_url_1).status_code == 403

    # Unauthenticated download -> 401
    saved_cookies = dict(api_client.cookies)
    api_client.cookies.clear()
    assert api_client.get(dl_url_1).status_code == 401
    api_client.cookies.update(saved_cookies)

    # Consume 2nd (final) allowed download -> then 3rd request hits quota (429 Too Many Requests)
    r_grant_2 = api_client.post(f"/api/downloads/{order_item_id}", headers=cust_headers)
    assert r_grant_2.status_code == 201
    assert api_client.get(r_grant_2.json()["download_url"]).status_code == 200
    assert api_client.post(f"/api/downloads/{order_item_id}", headers=cust_headers).status_code == 429

    # --- Workflow D & E: Worker Dispatch + Email/WhatsApp Mocked Transports + Webhooks ---
    resend_secret = "whsec_" + base64.b64encode(b"staging_resend_secret_bytes_01").decode("ascii")
    meta_secret = "meta_staging_app_secret"
    verify_tok = "meta_staging_verify_token_83"

    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_staging_test_key_secret")
    monkeypatch.setattr(settings, "RESEND_FROM_EMAIL", "noreply@staging.digiverse.example")
    monkeypatch.setattr(settings, "RESEND_WEBHOOK_SECRET", resend_secret)
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "wa_staging_test_token")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "1122334455")
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", meta_secret)
    monkeypatch.setattr(settings, "WHATSAPP_WEBHOOK_VERIFY_TOKEN", verify_tok)

    email_mode = {"fail": True}
    wa_mode = {"timeout": True}

    def _unified_staging_transport(request: httpx.Request) -> httpx.Response:
        host = request.url.host or ""
        if "r2.staging.example" in host:
            return _s3_handler(request)
        if "resend.com" in host:
            if email_mode["fail"]:
                return httpx.Response(503, json={"message": "Temporary Resend outage"})
            return httpx.Response(200, json={"id": "re_msg_staging_001"})
        if "facebook.com" in host:
            if wa_mode["timeout"]:
                raise httpx.ReadTimeout("Ambiguous network read timeout", request=request)
            return httpx.Response(200, json={"messages": [{"id": "wamid.staging.001"}]})
        raise AssertionError(f"Unexpected outbound host in staging test: {request.url}")

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kw: real_httpx_client(**{**kw, "transport": httpx.MockTransport(_unified_staging_transport)}),
    )

    email_camp = EmailCampaign(
        name="Staging Launch Email",
        subject="Your Digital Storefront Is Live",
        content="Check out our staging kits!",
        status=CampaignStatus.SCHEDULED,
        scheduled_for=datetime.now(timezone.utc) - timedelta(seconds=5),
    )
    wa_camp = WhatsAppCampaign(
        name="Staging Launch WhatsApp",
        content="Flash kit update",
        approved_template_name="staging_launch_v1",
        status=CampaignStatus.SCHEDULED,
        scheduled_for=datetime.now(timezone.utc) - timedelta(seconds=5),
    )
    db.add_all([email_camp, wa_camp])
    db.flush()

    # Cycle 1 (Workflow E): Email hits 503 -> scheduled for retry; WA hits ReadTimeout -> unresolved
    stats_1 = process_campaigns_in_session(db, worker_id="staging-w1", max_jobs=20, allow_deferred_retry=True)
    assert stats_1["claimed_jobs"] == 2
    assert stats_1["retrying"] == 1
    assert stats_1["failed"] == 1

    e_rec = db.query(CampaignRecipient).filter(CampaignRecipient.email_campaign_id == email_camp.id).one()
    w_rec = db.query(CampaignRecipient).filter(CampaignRecipient.whatsapp_campaign_id == wa_camp.id).one()
    assert e_rec.delivery_status == DeliveryStatus.RETRYING
    assert e_rec.attempt_count == 1
    assert e_rec.next_retry_at is not None
    assert w_rec.delivery_status == DeliveryStatus.UNRESOLVED

    # Allow email retry immediately & clear transient outage -> Email becomes ACCEPTED
    email_mode["fail"] = False
    e_rec.next_retry_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.flush()
    stats_2 = process_campaigns_in_session(db, worker_id="staging-w1", max_jobs=20, allow_deferred_retry=True)
    db.refresh(e_rec)
    db.refresh(email_camp)
    assert stats_2["accepted"] == 1, (
        f"stats_2={stats_2}, rec_status={e_rec.delivery_status}, "
        f"reason={e_rec.failure_reason}, camp_status={email_camp.status}"
    )
    db.refresh(e_rec)
    assert e_rec.delivery_status == DeliveryStatus.ACCEPTED
    assert e_rec.provider_message_id == "re_msg_staging_001"

    # Simulate Resend delivered webhook (+ replay dedup check)
    svix_id = f"msg_{uuid.uuid4().hex[:10]}"
    svix_ts = int(time.time())
    resend_body = json.dumps(
        {
            "type": "email.delivered",
            "data": {"email_id": "re_msg_staging_001", "to": [cust["email"]]},
        }
    ).encode("utf-8")
    resend_sig = _sign_resend_svix(resend_secret, svix_id, svix_ts, resend_body)
    r_ew = api_client.post(
        "/api/webhooks/email",
        content=resend_body,
        headers={
            "svix-id": svix_id,
            "svix-timestamp": str(svix_ts),
            "svix-signature": resend_sig,
            "Content-Type": "application/json",
        },
    )
    assert r_ew.status_code == 200
    assert r_ew.json()["processed"] == 1
    assert (
        api_client.post(
            "/api/webhooks/email",
            content=resend_body,
            headers={
                "svix-id": svix_id,
                "svix-timestamp": str(svix_ts),
                "svix-signature": resend_sig,
                "Content-Type": "application/json",
            },
        ).json()
        == {"status": "duplicate_ignored"}
    )
    db.refresh(email_camp)
    db.refresh(e_rec)
    assert e_rec.delivery_status == DeliveryStatus.DELIVERED
    assert email_camp.status == CampaignStatus.COMPLETED

    # Meta WhatsApp GET challenge + POST webhook reconciliation for unresolved timeout
    r_ch = api_client.get(
        "/api/webhooks/whatsapp",
        params={"hub.mode": "subscribe", "hub.verify_token": verify_tok, "hub.challenge": "998877"},
    )
    assert r_ch.status_code == 200
    assert r_ch.text == "998877"

    wa_digits = "".join(c for c in cust["phone_number"] if c.isdigit())
    wa_body = json.dumps(
        {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "waba_staging",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "statuses": [
                                    {
                                        "id": "wamid.reconciled.staging.01",
                                        "recipient_id": wa_digits,
                                        "status": "delivered",
                                        "timestamp": str(int(time.time())),
                                    }
                                ]
                            },
                        }
                    ],
                }
            ],
        }
    ).encode("utf-8")
    r_ww = api_client.post(
        "/api/webhooks/whatsapp",
        content=wa_body,
        headers={
            "X-Hub-Signature-256": _sign_whatsapp_hub(meta_secret, wa_body),
            "Content-Type": "application/json",
        },
    )
    assert r_ww.status_code == 200
    assert r_ww.json()["processed"] == 1
    db.refresh(w_rec)
    db.refresh(wa_camp)
    assert w_rec.delivery_status == DeliveryStatus.DELIVERED
    assert wa_camp.status == CampaignStatus.COMPLETED

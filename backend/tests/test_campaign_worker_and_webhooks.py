"""Phase 8.2 comprehensive tests: persistent worker, retries, providers, concurrency, and webhooks.

Runs strictly against `digiverse_test` (`TEST_DATABASE_URL`) using mock HTTP transports and
development providers — never touches production `digiverse` or external live APIs.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.logging import app_logger
from app.core.security import get_password_hash
from app.models.campaign import (
    CampaignRecipient,
    EmailCampaign,
    MarketingWebhookEvent,
    WhatsAppCampaign,
    WorkerHeartbeat,
)
from app.models.customer import Customer
from app.models.enums import AccountStatus, CampaignStatus, DeliveryStatus, MessageChannel
from app.services.campaign_worker import (
    calculate_backoff_seconds,
    claim_and_enqueue_due_campaigns,
    claim_recipient_batch,
    process_campaigns_in_session,
    run_worker_cycle,
)
from app.services.email_service import (
    EmailDeliveryError,
    ProductionEmailProvider,
    dev_email_provider,
)
from app.services.whatsapp_service import (
    MetaWhatsAppCloudProvider,
    WhatsAppDeliveryError,
    dev_whatsapp_provider,
)
from app.worker import run_worker_loop
from tests.conftest import _test_database_url
from tests.test_operations import _login_admin, _register_customer


def _sign_resend_webhook(secret: str, svix_id: str, ts: int, raw_body: bytes) -> str:
    raw_secret = secret[6:] if secret.startswith("whsec_") else secret
    secret_bytes = base64.b64decode(raw_secret) if secret.startswith("whsec_") else raw_secret.encode("utf-8")
    signed = f"{svix_id}.{ts}.{raw_body.decode('utf-8')}".encode("utf-8")
    sig_b64 = base64.b64encode(hmac.new(secret_bytes, signed, hashlib.sha256).digest()).decode("utf-8")
    return f"v1,{sig_b64}"


def _sign_whatsapp_webhook(app_secret: str, raw_body: bytes) -> str:
    digest = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


# ===========================================================================
# 1. WORKER DISCOVERY, SCHEDULING, OPT-OUT AFTER QUEUEING & GRACEFUL SHUTDOWN
# ===========================================================================


def test_worker_discovers_scheduled_respects_future_and_midflight_optout(api_client, db):
    dev_email_provider.clear()
    _, c_active = _register_customer(api_client, name="Active OptIn", email_consent=True)
    api_client.cookies.clear()
    _, c_unsub = _register_customer(api_client, name="Late Unsub", email_consent=True)
    api_client.cookies.clear()

    admin_headers = _login_admin(api_client, db)
    r_due = api_client.post(
        "/api/admin/campaigns/email",
        json={"name": "Due Now", "subject": "Hello!", "content": "Launch offer"},
        headers=admin_headers,
    )
    due_id = uuid.UUID(r_due.json()["id"])

    r_future = api_client.post(
        "/api/admin/campaigns/email",
        json={"name": "Future Camp", "subject": "Later!", "content": "Next week"},
        headers=admin_headers,
    )
    future_id = uuid.UUID(r_future.json()["id"])

    # Schedule one due now and one 1 hour in the future
    assert (
        api_client.post(f"/api/admin/campaigns/email/{due_id}/schedule", headers=admin_headers).status_code
        == 200
    )
    future_ts = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    assert (
        api_client.post(
            f"/api/admin/campaigns/email/{future_id}/schedule",
            json={"scheduled_for": future_ts},
            headers=admin_headers,
        ).status_code
        == 200
    )

    # Queue recipients for the due campaign first, THEN unsubscribe c_unsub BEFORE sending
    claim_and_enqueue_due_campaigns(db, worker_id="test-w1")
    unsub_cust = db.get(Customer, uuid.UUID(c_unsub["id"]))
    unsub_cust.email_marketing_consent = False
    db.flush()

    res = process_campaigns_in_session(db, worker_id="test-w1", allow_deferred_retry=True)
    assert res["accepted"] == 1
    assert res["skipped"] == 1

    # Provider accepted for active subscriber and skipped late opt-out; campaign stays PROCESSING
    # until webhook confirms actual delivery (provider acceptance != confirmed delivery).
    due_camp = db.get(EmailCampaign, due_id)
    future_camp = db.get(EmailCampaign, future_id)
    assert due_camp.status == CampaignStatus.PROCESSING
    assert due_camp.completed_at is None
    assert future_camp.status == CampaignStatus.SCHEDULED

    sent_emails = [m["email"] for m in dev_email_provider.sent_notifications]
    assert c_active["email"] in sent_emails
    assert c_unsub["email"] not in sent_emails

    # Verify detail endpoint accurately exposes queued/accepted/skipped counts
    detail = api_client.get(f"/api/admin/campaigns/email/{due_id}", headers=admin_headers)
    assert detail.status_code == 200
    djson = detail.json()
    assert djson["accepted_count"] == 1
    assert djson["skipped_count"] == 1
    assert djson["delivered_count"] == 0


def test_worker_loop_graceful_shutdown(monkeypatch):
    url = _test_database_url()
    eng = create_engine(url, pool_pre_ping=True)
    LocalSession = sessionmaker(bind=eng, autocommit=False, autoflush=False, expire_on_commit=False)

    monkeypatch.setattr("app.worker.SessionLocal", LocalSession)
    monkeypatch.setattr("app.worker.engine", eng)
    monkeypatch.setattr("app.worker.run_worker_cycle", lambda *args, **kwargs: {"claimed_jobs": 0})

    stop_event = threading.Event()
    stop_event.set()
    rc = run_worker_loop(poll_interval_seconds=30, batch_size=10, run_once=False, stop_event=stop_event)
    assert rc == 0

    with LocalSession() as s:
        hbs = s.scalars(select(WorkerHeartbeat).where(WorkerHeartbeat.status == "stopped")).all()
        assert len(hbs) >= 1
        for hb in hbs:
            if hb.worker_id.startswith("worker-"):
                s.delete(hb)
        s.commit()
    eng.dispose()


# ===========================================================================
# 2. REAL POSTGRESQL MULTI-WORKER CONCURRENCY & STALE LOCK RECOVERY
# ===========================================================================


def test_postgresql_concurrent_workers_skip_locked_no_duplicate_delivery(monkeypatch):
    """Run two real concurrent PostgreSQL worker threads against committed rows using SKIP LOCKED."""
    url = _test_database_url()
    eng = create_engine(url, pool_pre_ping=True, pool_size=6)
    SessionFactory = sessionmaker(bind=eng, autocommit=False, autoflush=False, expire_on_commit=False)

    dev_email_provider.clear()
    created_cust_ids: list[uuid.UUID] = []
    camp_id: uuid.UUID | None = None
    worker_ids = [f"conc-w1-{uuid.uuid4().hex[:6]}", f"conc-w2-{uuid.uuid4().hex[:6]}"]

    try:
        with SessionFactory() as setup_db:
            camp = EmailCampaign(
                name=f"Concurrent Blast {uuid.uuid4().hex[:6]}",
                subject="Concurrency Subject",
                content="Hello concurrent creator",
                status=CampaignStatus.SCHEDULED,
                scheduled_for=datetime.now(timezone.utc) - timedelta(minutes=1),
            )
            setup_db.add(camp)
            setup_db.flush()
            camp_id = camp.id

            for idx in range(12):
                cust = Customer(
                    full_name=f"Worker Target {idx}",
                    email=f"conc-{idx}-{uuid.uuid4().hex[:8]}@example.test",
                    password_hash=get_password_hash("StrongPass!123"),
                    account_status=AccountStatus.ACTIVE,
                    email_marketing_consent=True,
                )
                setup_db.add(cust)
                setup_db.flush()
                created_cust_ids.append(cust.id)
            setup_db.commit()

        # Slow down provider slightly so both concurrent worker threads truly contend cleanly
        orig_send = dev_email_provider.send_transactional_email
        sent_lock = threading.Lock()
        sent_counter: dict[str, int] = {}

        def _tracked_send(**kwargs):
            time.sleep(0.02)
            with sent_lock:
                sent_counter[kwargs["email"]] = sent_counter.get(kwargs["email"], 0) + 1
            return orig_send(**kwargs)

        monkeypatch.setattr(dev_email_provider, "send_transactional_email", _tracked_send)

        def _run_worker(wid: str) -> dict[str, int]:
            return run_worker_cycle(SessionFactory, worker_id=wid, batch_size=6)

        # Drain across concurrent worker invocations until queue empty
        cycles = []
        for _ in range(3):
            with ThreadPoolExecutor(max_workers=2) as pool:
                f1 = pool.submit(_run_worker, worker_ids[0])
                f2 = pool.submit(_run_worker, worker_ids[1])
                cycles.extend([f1.result(), f2.result()])

        assert len(sent_counter) == 12
        assert all(cnt == 1 for cnt in sent_counter.values()), f"Duplicate send detected: {sent_counter}"

        with SessionFactory() as verify_db:
            final_camp = verify_db.get(EmailCampaign, camp_id)
            # All 12 accepted by provider, awaiting webhook delivery confirmation -> still PROCESSING
            assert final_camp.status == CampaignStatus.PROCESSING
            assert final_camp.completed_at is None
            recs = verify_db.scalars(
                select(CampaignRecipient).where(CampaignRecipient.email_campaign_id == camp_id)
            ).all()
            assert len(recs) == 12
            assert all(r.delivery_status == DeliveryStatus.ACCEPTED for r in recs)
            assert all(r.attempt_count == 1 for r in recs)
    finally:
        with SessionFactory() as cleanup_db:
            if camp_id:
                camp_obj = cleanup_db.get(EmailCampaign, camp_id)
                if camp_obj:
                    cleanup_db.delete(camp_obj)
            for cid in created_cust_ids:
                cust_obj = cleanup_db.get(Customer, cid)
                if cust_obj:
                    cleanup_db.delete(cust_obj)
            for wid in worker_ids:
                hb = cleanup_db.get(WorkerHeartbeat, wid)
                if hb:
                    cleanup_db.delete(hb)
            cleanup_db.commit()
        eng.dispose()


def test_stale_lock_recovery_after_simulated_worker_crash(db, make_customer):
    """Simulate a crashed worker leaving a job in `processing` beyond stale timeout."""
    dev_email_provider.clear()
    c1 = make_customer(email_marketing_consent=True, account_status=AccountStatus.ACTIVE)
    camp = EmailCampaign(
        name="Crash Recovery Campaign",
        subject="Crash Recovery",
        content="Recovered smoothly",
        status=CampaignStatus.PROCESSING,
        started_at=datetime.now(timezone.utc) - timedelta(minutes=15),
    )
    db.add(camp)
    db.flush()

    stale_rec = CampaignRecipient(
        channel=MessageChannel.EMAIL,
        email_campaign_id=camp.id,
        customer_id=c1.id,
        delivery_status=DeliveryStatus.PROCESSING,
        attempt_count=1,
        max_attempts=3,
        locked_by="crashed-worker-99",
        locked_at=datetime.now(timezone.utc) - timedelta(minutes=20),
        idempotency_key=f"dv-crash-{uuid.uuid4().hex[:10]}",
    )
    db.add(stale_rec)
    db.flush()

    res = process_campaigns_in_session(db, worker_id="healthy-worker-1", allow_deferred_retry=True)
    assert res["accepted"] == 1

    db.refresh(stale_rec)
    db.refresh(camp)
    assert stale_rec.delivery_status == DeliveryStatus.ACCEPTED
    assert stale_rec.attempt_count == 2
    assert stale_rec.locked_by is None
    assert camp.status == CampaignStatus.PROCESSING


# ===========================================================================
# 3. RETRIES, BACKOFF, HTTP 429, TIMEOUTS & PERMANENT FAILURE CLASSIFICATION
# ===========================================================================


def test_retry_backoff_429_permanent_errors_and_exhaustion(db, make_customer, monkeypatch):
    dev_email_provider.clear()
    c_retry_ok = make_customer(email_marketing_consent=True, account_status=AccountStatus.ACTIVE)
    c_429 = make_customer(email_marketing_consent=True, account_status=AccountStatus.ACTIVE)
    c_perm = make_customer(email_marketing_consent=True, account_status=AccountStatus.ACTIVE)

    camp = EmailCampaign(
        name="Retry Matrix Campaign",
        subject="Retry Matrix",
        content="Testing backoff",
        status=CampaignStatus.PROCESSING,
    )
    db.add(camp)
    db.flush()

    for cust, max_att in ((c_retry_ok, 3), (c_429, 2), (c_perm, 5)):
        db.add(
            CampaignRecipient(
                channel=MessageChannel.EMAIL,
                email_campaign_id=camp.id,
                customer_id=cust.id,
                delivery_status=DeliveryStatus.QUEUED,
                max_attempts=max_att,
                idempotency_key=f"dv-mat-{cust.id.hex[:8]}-{uuid.uuid4().hex[:4]}",
            )
        )
    db.flush()

    # Configure simulated errors
    dev_email_provider.simulate_error_for[c_retry_ok.email.lower()] = EmailDeliveryError(
        "Temporary upstream 503", code="http_503", retryable=True, status_code=503
    )
    dev_email_provider.simulate_error_for[c_429.email.lower()] = EmailDeliveryError(
        "Rate limited", code="rate_limited", retryable=True, status_code=429, retry_after_seconds=120
    )
    dev_email_provider.simulate_error_for[c_perm.email.lower()] = EmailDeliveryError(
        "Validation rejected 422", code="http_422", retryable=False, status_code=422
    )

    monkeypatch.setattr(settings, "CAMPAIGN_RETRY_BASE_SECONDS", 30)
    monkeypatch.setattr(settings, "CAMPAIGN_RETRY_MAX_BACKOFF_SECONDS", 1800)

    # Pass 1: c_retry_ok & c_429 -> RETRYING with backoff; c_perm -> terminal FAILED immediately (attempt 1)
    process_campaigns_in_session(db, worker_id="w-retry", allow_deferred_retry=True)
    recs = {
        r.customer_id: r
        for r in db.scalars(
            select(CampaignRecipient).where(CampaignRecipient.email_campaign_id == camp.id)
        ).all()
    }
    assert recs[c_perm.id].delivery_status == DeliveryStatus.FAILED
    assert recs[c_perm.id].attempt_count == 1
    assert recs[c_perm.id].is_retryable_error is False

    assert recs[c_429.id].delivery_status == DeliveryStatus.RETRYING
    assert recs[c_429.id].error_code == "rate_limited"
    assert recs[c_429.id].next_retry_at > datetime.now(timezone.utc) + timedelta(seconds=100)

    assert recs[c_retry_ok.id].delivery_status == DeliveryStatus.RETRYING
    assert calculate_backoff_seconds(2) == 60

    db.refresh(camp)
    assert camp.status == CampaignStatus.PROCESSING

    # Make both retrying rows due now; let c_retry_ok succeed and let c_429 exhaust max_attempts=2
    dev_email_provider.simulate_error_for.pop(c_retry_ok.email.lower())
    recs[c_retry_ok.id].next_retry_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    recs[c_429.id].next_retry_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.flush()

    process_campaigns_in_session(db, worker_id="w-retry", allow_deferred_retry=True)
    db.refresh(recs[c_retry_ok.id])
    db.refresh(recs[c_429.id])
    db.refresh(camp)

    assert recs[c_retry_ok.id].delivery_status == DeliveryStatus.ACCEPTED
    assert recs[c_retry_ok.id].attempt_count == 2
    assert recs[c_429.id].delivery_status == DeliveryStatus.FAILED
    assert recs[c_429.id].attempt_count == 2
    # c_retry_ok is ACCEPTED (pending webhook confirmation), so campaign stays PROCESSING until resolved
    assert camp.status == CampaignStatus.PROCESSING

    # Confirm c_retry_ok via webhook -> now 1 DELIVERED + 2 FAILED => PARTIALLY_COMPLETED
    recs[c_retry_ok.id].delivery_status = DeliveryStatus.DELIVERED
    recs[c_retry_ok.id].delivered_at = datetime.now(timezone.utc)
    from app.services.campaign_worker import recompute_campaign_status

    recompute_campaign_status(db, MessageChannel.EMAIL, camp.id)
    db.refresh(camp)
    assert camp.status == CampaignStatus.PARTIALLY_COMPLETED


def test_resend_and_whatsapp_adapters_mock_http_and_timeouts(monkeypatch):
    """Verify Resend Idempotency-Key + Meta WhatsApp Cloud adapter behavior with MockTransport."""
    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_dummy_123456")
    monkeypatch.setattr(settings, "RESEND_FROM_EMAIL", "noreply@digiverse.test")
    monkeypatch.setattr(settings, "RESEND_FROM_NAME", "DIGI-VERSE")
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "wa_test_token_dummy")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "1234567890")
    monkeypatch.setattr(settings, "WHATSAPP_GRAPH_API_VERSION", "v20.0")

    captured_resend_headers = []
    call_num = {"resend": 0}

    def resend_handler(request: httpx.Request) -> httpx.Response:
        call_num["resend"] += 1
        captured_resend_headers.append(dict(request.headers))
        if call_num["resend"] == 1:
            raise httpx.ReadTimeout("Simulated Resend read timeout")
        if call_num["resend"] == 2:
            return httpx.Response(429, headers={"Retry-After": "45"}, json={"message": "Rate limit"})
        return httpx.Response(200, json={"id": "re_msg_verified_99"})

    real_httpx_client = httpx.Client
    monkeypatch.setattr(
        "app.services.email_service.httpx.Client",
        lambda **kw: real_httpx_client(transport=httpx.MockTransport(resend_handler), **kw),
    )

    ep = ProductionEmailProvider()
    with pytest.raises(EmailDeliveryError) as e1:
        ep.send_transactional_email(
            email="buyer@example.test",
            template_name="camp:test",
            subject="Hi",
            body="Body",
            category="marketing",
            idempotency_key="idem-key-abc",
        )
    assert e1.value.retryable is True
    assert e1.value.code == "provider_timeout"

    with pytest.raises(EmailDeliveryError) as e2:
        ep.send_transactional_email(
            email="buyer@example.test",
            template_name="camp:test",
            subject="Hi",
            body="Body",
            category="marketing",
            idempotency_key="idem-key-abc",
        )
    assert e2.value.retryable is True
    assert e2.value.status_code == 429
    assert e2.value.retry_after_seconds == 45

    msg_id = ep.send_transactional_email(
        email="buyer@example.test",
        template_name="camp:test",
        subject="Hi",
        body="Body",
        category="marketing",
        idempotency_key="idem-key-abc",
    )
    assert msg_id == "re_msg_verified_99"
    assert all(h.get("idempotency-key") == "idem-key-abc" for h in captured_resend_headers)

    # Meta WhatsApp Cloud adapter: ConnectError retryable vs ReadTimeout ambiguous suppression
    wa_mode = {"mode": "connect"}

    def wa_handler(request: httpx.Request) -> httpx.Response:
        assert "/v20.0/1234567890/messages" in str(request.url)
        if wa_mode["mode"] == "connect":
            raise httpx.ConnectError("Network unreachable")
        if wa_mode["mode"] == "read_timeout":
            raise httpx.ReadTimeout("Timeout after submission")
        return httpx.Response(200, json={"messages": [{"id": "wamid.cloud.999"}]})

    monkeypatch.setattr(
        "app.services.whatsapp_service.httpx.Client",
        lambda **kw: real_httpx_client(transport=httpx.MockTransport(wa_handler), **kw),
    )

    wp = MetaWhatsAppCloudProvider()
    with pytest.raises(WhatsAppDeliveryError) as w1:
        wp.send_template_message("+919876543210", "flash_v1", "Hi")
    assert w1.value.retryable is True
    assert w1.value.is_ambiguous_timeout is False

    wa_mode["mode"] = "read_timeout"
    with pytest.raises(WhatsAppDeliveryError) as w2:
        wp.send_template_message("+919876543210", "flash_v1", "Hi")
    assert w2.value.retryable is False
    assert w2.value.is_ambiguous_timeout is True
    assert w2.value.code == "timeout_after_submission"

    wa_mode["mode"] = "ok"
    wamid = wp.send_template_message("+919876543210", "flash_v1", "Hi")
    assert wamid == "wamid.cloud.999"


# ===========================================================================
# 4. WEBHOOK SECURITY, REPLAY/DUPLICATES & OUT-OF-ORDER PROTECTION
# ===========================================================================


def test_email_webhook_security_idempotency_suppression_and_out_of_order(api_client, db, make_customer, monkeypatch):
    secret_raw = base64.b64encode(b"super_secret_resend_key_12345678").decode("utf-8")
    webhook_secret = f"whsec_{secret_raw}"
    monkeypatch.setattr(settings, "RESEND_WEBHOOK_SECRET", webhook_secret)

    c_deliv = make_customer(email_marketing_consent=True, account_status=AccountStatus.ACTIVE)
    c_comp = make_customer(email_marketing_consent=True, account_status=AccountStatus.ACTIVE)
    camp = EmailCampaign(name="Webhook Camp", subject="Sub", content="Body", status=CampaignStatus.COMPLETED)
    db.add(camp)
    db.flush()

    r1 = CampaignRecipient(
        channel=MessageChannel.EMAIL,
        email_campaign_id=camp.id,
        customer_id=c_deliv.id,
        delivery_status=DeliveryStatus.ACCEPTED,
        provider_message_id="re_live_101",
    )
    r2 = CampaignRecipient(
        channel=MessageChannel.EMAIL,
        email_campaign_id=camp.id,
        customer_id=c_comp.id,
        delivery_status=DeliveryStatus.ACCEPTED,
        provider_message_id="re_live_102",
    )
    db.add_all([r1, r2])
    db.flush()

    now_ts = int(time.time())
    body1 = json.dumps({"type": "email.delivered", "data": {"email_id": "re_live_101"}}).encode("utf-8")

    # 1. Invalid signature -> 401
    r_bad = api_client.post(
        "/api/webhooks/email",
        content=body1,
        headers={
            "svix-id": "msg_invalid_1",
            "svix-timestamp": str(now_ts),
            "svix-signature": "v1,invalidsig==",
            "Content-Type": "application/json",
        },
    )
    assert r_bad.status_code == 401

    # 2. Stale timestamp replay outside window -> 401
    old_ts = now_ts - 3600
    old_sig = _sign_resend_webhook(webhook_secret, "msg_old_1", old_ts, body1)
    r_stale = api_client.post(
        "/api/webhooks/email",
        content=body1,
        headers={
            "svix-id": "msg_old_1",
            "svix-timestamp": str(old_ts),
            "svix-signature": old_sig,
            "Content-Type": "application/json",
        },
    )
    assert r_stale.status_code == 401

    # 3. Valid email.delivered -> transitions ACCEPTED -> DELIVERED
    sig1 = _sign_resend_webhook(webhook_secret, "msg_evt_deliv", now_ts, body1)
    r_ok = api_client.post(
        "/api/webhooks/email",
        content=body1,
        headers={
            "svix-id": "msg_evt_deliv",
            "svix-timestamp": str(now_ts),
            "svix-signature": sig1,
            "Content-Type": "application/json",
        },
    )
    assert r_ok.status_code == 200
    assert r_ok.json() == {"status": "ok", "processed": 1, "duplicates": 0}
    db.refresh(r1)
    assert r1.delivery_status == DeliveryStatus.DELIVERED
    assert r1.delivered_at is not None

    # 4. Duplicate event -> idempotent ignore
    r_dup = api_client.post(
        "/api/webhooks/email",
        content=body1,
        headers={
            "svix-id": "msg_evt_deliv",
            "svix-timestamp": str(now_ts),
            "svix-signature": sig1,
            "Content-Type": "application/json",
        },
    )
    assert r_dup.status_code == 200
    assert r_dup.json()["status"] == "duplicate_ignored"

    # 5. Out-of-order delayed email.sent / email.bounced CANNOT downgrade DELIVERED
    body_late_sent = json.dumps({"type": "email.sent", "data": {"email_id": "re_live_101"}}).encode("utf-8")
    sig_late = _sign_resend_webhook(webhook_secret, "msg_evt_late_sent", now_ts, body_late_sent)
    r_ooo = api_client.post(
        "/api/webhooks/email",
        content=body_late_sent,
        headers={
            "svix-id": "msg_evt_late_sent",
            "svix-timestamp": str(now_ts),
            "svix-signature": sig_late,
            "Content-Type": "application/json",
        },
    )
    assert r_ooo.status_code == 200
    assert r_ooo.json()["processed"] == 0
    db.refresh(r1)
    assert r1.delivery_status == DeliveryStatus.DELIVERED

    # 6. email.complained -> marks SUPPRESSED, opts customer out & transitions campaign to PARTIALLY_COMPLETED
    body_comp = json.dumps({"type": "email.complained", "data": {"email_id": "re_live_102"}}).encode("utf-8")
    sig_comp = _sign_resend_webhook(webhook_secret, "msg_evt_comp", now_ts, body_comp)
    r_comp_resp = api_client.post(
        "/api/webhooks/email",
        content=body_comp,
        headers={
            "svix-id": "msg_evt_comp",
            "svix-timestamp": str(now_ts),
            "svix-signature": sig_comp,
            "Content-Type": "application/json",
        },
    )
    assert r_comp_resp.status_code == 200
    assert r_comp_resp.json()["processed"] == 1
    db.refresh(r2)
    db.refresh(c_comp)
    db.refresh(camp)
    assert r2.delivery_status == DeliveryStatus.SUPPRESSED
    assert c_comp.email_marketing_consent is False
    assert camp.status == CampaignStatus.PARTIALLY_COMPLETED


def test_whatsapp_webhook_verification_signature_oversize_and_out_of_order(
    api_client, db, make_customer, monkeypatch
):
    monkeypatch.setattr(settings, "WHATSAPP_WEBHOOK_VERIFY_TOKEN", "verify_tok_test_82")
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", "meta_app_secret_test_82")

    # 1. GET verification valid & invalid
    r_bad_tok = api_client.get(
        "/api/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=wrong&hub.challenge=chal_999"
    )
    assert r_bad_tok.status_code == 403

    r_good_tok = api_client.get(
        "/api/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=verify_tok_test_82&hub.challenge=chal_999"
    )
    assert r_good_tok.status_code == 200
    assert r_good_tok.text == "chal_999"

    # Seed WA recipient in ACCEPTED
    cust = make_customer(
        whatsapp_marketing_consent=True,
        phone_number="+919876543211",
        account_status=AccountStatus.ACTIVE,
    )
    camp = WhatsAppCampaign(
        name="WA Webhook",
        content="Offer",
        approved_template_name="tpl_v1",
        status=CampaignStatus.PROCESSING,
    )
    db.add(camp)
    db.flush()
    rec = CampaignRecipient(
        channel=MessageChannel.WHATSAPP,
        whatsapp_campaign_id=camp.id,
        customer_id=cust.id,
        delivery_status=DeliveryStatus.ACCEPTED,
        provider_message_id="wamid.wh.101",
    )
    db.add(rec)
    db.flush()

    def _wa_payload(status_val: str, ts: str) -> bytes:
        return json.dumps(
            {
                "object": "whatsapp_business_account",
                "entry": [
                    {
                        "id": "waba_1",
                        "changes": [
                            {
                                "field": "messages",
                                "value": {
                                    "statuses": [
                                        {
                                            "id": "wamid.wh.101",
                                            "status": status_val,
                                            "timestamp": ts,
                                        }
                                    ]
                                },
                            }
                        ],
                    }
                ],
            }
        ).encode("utf-8")

    read_body = _wa_payload("read", "1732200020")
    read_sig = _sign_whatsapp_webhook("meta_app_secret_test_82", read_body)

    # 2. Invalid POST signature -> 401
    assert (
        api_client.post(
            "/api/webhooks/whatsapp",
            content=read_body,
            headers={"X-Hub-Signature-256": "sha256=deadbeef", "Content-Type": "application/json"},
        ).status_code
        == 401
    )

    # 3. Malformed JSON with valid signature -> 400
    bad_json = b"{not-json"
    assert (
        api_client.post(
            "/api/webhooks/whatsapp",
            content=bad_json,
            headers={
                "X-Hub-Signature-256": _sign_whatsapp_webhook("meta_app_secret_test_82", bad_json),
                "Content-Type": "application/json",
            },
        ).status_code
        == 400
    )

    # 4. Oversized payload -> 413
    monkeypatch.setattr(settings, "MAX_WEBHOOK_PAYLOAD_BYTES", 50)
    big_sig = _sign_whatsapp_webhook("meta_app_secret_test_82", read_body)
    assert (
        api_client.post(
            "/api/webhooks/whatsapp",
            content=read_body,
            headers={"X-Hub-Signature-256": big_sig, "Content-Type": "application/json"},
        ).status_code
        == 413
    )
    monkeypatch.setattr(settings, "MAX_WEBHOOK_PAYLOAD_BYTES", 1048576)

    # 5. Out-of-order READ arrives first -> transitions ACCEPTED -> READ
    r_read = api_client.post(
        "/api/webhooks/whatsapp",
        content=read_body,
        headers={"X-Hub-Signature-256": read_sig, "Content-Type": "application/json"},
    )
    assert r_read.status_code == 200
    assert r_read.json() == {"status": "ok", "processed": 1, "duplicates": 0}
    db.refresh(rec)
    db.refresh(camp)
    assert rec.delivery_status == DeliveryStatus.READ
    assert camp.status == CampaignStatus.COMPLETED

    # 6. Duplicate READ -> ignored
    r_read_dup = api_client.post(
        "/api/webhooks/whatsapp",
        content=read_body,
        headers={"X-Hub-Signature-256": read_sig, "Content-Type": "application/json"},
    )
    assert r_read_dup.status_code == 200
    assert r_read_dup.json() == {"status": "ok", "processed": 0, "duplicates": 1}

    # 7. Late DELIVERED or SENT cannot downgrade READ
    deliv_body = _wa_payload("delivered", "1732200010")
    r_late_deliv = api_client.post(
        "/api/webhooks/whatsapp",
        content=deliv_body,
        headers={
            "X-Hub-Signature-256": _sign_whatsapp_webhook("meta_app_secret_test_82", deliv_body),
            "Content-Type": "application/json",
        },
    )
    assert r_late_deliv.status_code == 200
    assert r_late_deliv.json() == {"status": "ok", "processed": 0, "duplicates": 0}
    db.refresh(rec)
    assert rec.delivery_status == DeliveryStatus.READ


# ===========================================================================
# 5. LOG REDACTION VERIFICATION
# ===========================================================================


def test_logs_never_leak_provider_credentials(caplog, monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_secret_never_log_98765")
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "wa_secret_never_log_12345")

    def _err_resend(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "Internal failure"})

    real_httpx_client = httpx.Client
    monkeypatch.setattr(
        "app.services.email_service.httpx.Client",
        lambda **kw: real_httpx_client(transport=httpx.MockTransport(_err_resend), **kw),
    )

    caplog.set_level(logging.WARNING, logger="digiverse")
    with pytest.raises(EmailDeliveryError):
        ProductionEmailProvider().send_transactional_email(
            email="user@example.test",
            template_name="camp:secretcheck",
            subject="Subject",
            body="Private Body",
            category="marketing",
        )

    combined = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "re_secret_never_log_98765" not in combined
    assert "wa_secret_never_log_12345" not in combined
    assert "user@example.test" not in combined


# ===========================================================================
# 6. AUDIT VERIFICATION: WHATSAPP AMBIGUOUS TIMEOUT RECONCILIATION & FENCING
# ===========================================================================


def test_audit_ambiguous_whatsapp_read_timeout_and_webhook_reconciliation(
    api_client, db, make_customer, monkeypatch
):
    """Audit 2 & Audit 3:
    1. Post-submission ReadTimeout does NOT blindly retry, is NOT silently marked completed/delivered,
       and marks recipient `unresolved` visible to admins.
    2. Valid Meta webhook with `recipient_id` binds `wamid`, reconciles `unresolved` -> `delivered`,
       and completes campaign accurately.
    """
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "wa_live_test_token")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "9988776655")
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", "meta_reconcile_secret")

    cust = make_customer(
        whatsapp_marketing_consent=True,
        phone_number="+919811223344",
        account_status=AccountStatus.ACTIVE,
    )
    admin_headers = _login_admin(api_client, db)

    camp = WhatsAppCampaign(
        name="Audit 3 Timeout Reconciliation",
        content="Flash launch alert",
        approved_template_name="flash_v1",
        status=CampaignStatus.SCHEDULED,
        scheduled_for=datetime.now(timezone.utc) - timedelta(seconds=5),
    )
    db.add(camp)
    db.flush()

    calls = {"wa": 0}
    real_httpx_client = httpx.Client

    def _wa_timeout_handler(request: httpx.Request) -> httpx.Response:
        calls["wa"] += 1
        raise httpx.ReadTimeout("Simulated timeout after Meta submission")

    monkeypatch.setattr(
        "app.services.whatsapp_service.httpx.Client",
        lambda **kw: real_httpx_client(transport=httpx.MockTransport(_wa_timeout_handler), **kw),
    )

    # Pass 1: Worker hits ReadTimeout -> marks UNRESOLVED (no provider_message_id yet)
    process_campaigns_in_session(db, worker_id="w-audit-3", allow_deferred_retry=True)
    assert calls["wa"] == 1

    rec = db.scalar(
        select(CampaignRecipient).where(CampaignRecipient.whatsapp_campaign_id == camp.id)
    )
    db.refresh(camp)
    assert rec.delivery_status == DeliveryStatus.UNRESOLVED
    assert rec.provider_message_id is None
    assert rec.error_code == "timeout_after_submission"
    assert rec.is_retryable_error is False
    # Campaign MUST NOT be marked completed or delivered
    assert camp.status == CampaignStatus.PROCESSING
    assert camp.completed_at is None

    # Pass 2: Subsequent worker run MUST NOT blindly re-send or reclaim UNRESOLVED row
    res2 = process_campaigns_in_session(db, worker_id="w-audit-3-pass2", allow_deferred_retry=True)
    assert res2["claimed_jobs"] == 0
    assert calls["wa"] == 1

    # Visible to admins via campaign detail API
    r_detail = api_client.get(f"/api/admin/campaigns/whatsapp/{camp.id}", headers=admin_headers)
    assert r_detail.status_code == 200
    djson = r_detail.json()
    assert djson["unresolved_count"] == 1
    assert djson["delivered_count"] == 0
    assert djson["failure_summary"].get("timeout_after_submission") == 1

    # Subsequent valid Meta webhook carrying `recipient_id` reconciles the UNRESOLVED row
    wh_body = json.dumps(
        {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "waba_audit",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "statuses": [
                                    {
                                        "id": "wamid.reconciled.777",
                                        "status": "delivered",
                                        "timestamp": "1732200500",
                                        "recipient_id": "919811223344",
                                    }
                                ]
                            },
                        }
                    ],
                }
            ],
        }
    ).encode("utf-8")

    r_wh = api_client.post(
        "/api/webhooks/whatsapp",
        content=wh_body,
        headers={
            "X-Hub-Signature-256": _sign_whatsapp_webhook("meta_reconcile_secret", wh_body),
            "Content-Type": "application/json",
        },
    )
    assert r_wh.status_code == 200
    assert r_wh.json() == {"status": "ok", "processed": 1, "duplicates": 0}

    db.refresh(rec)
    db.refresh(camp)
    assert rec.provider_message_id == "wamid.reconciled.777"
    assert rec.delivery_status == DeliveryStatus.DELIVERED
    assert rec.error_code is None
    assert rec.provider_response_metadata.get("reconciled_from_ambiguous_timeout") is True
    assert camp.status == CampaignStatus.COMPLETED
    assert camp.completed_at is not None


def test_audit_whatsapp_batch_dedup_progression_and_lock_fencing(
    api_client, db, make_customer, monkeypatch
):
    """Audit 1 & Audit 4:
    - Legitimate status progression `accepted -> sent -> delivered -> read` succeeds.
    - Repeated status entries inside a single batch and repeated status with new timestamp are ignored safely.
    - Lock-owner fencing rejects stale worker completion if another worker reclaimed the job.
    """
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", "meta_seq_secret")
    cust = make_customer(
        whatsapp_marketing_consent=True,
        phone_number="+919822334455",
        account_status=AccountStatus.ACTIVE,
    )
    camp = WhatsAppCampaign(
        name="Audit 1 & 4 Check",
        content="Progression check",
        approved_template_name="prog_v1",
        status=CampaignStatus.PROCESSING,
    )
    db.add(camp)
    db.flush()
    rec = CampaignRecipient(
        channel=MessageChannel.WHATSAPP,
        whatsapp_campaign_id=camp.id,
        customer_id=cust.id,
        delivery_status=DeliveryStatus.ACCEPTED,
        provider_message_id="wamid.prog.1",
        locked_by="worker-B",
        locked_at=datetime.now(timezone.utc),
    )
    db.add(rec)
    db.flush()

    # Batch containing: accepted->sent, duplicate identical entry in same POST, AND repeated sent at ts+5
    batch_body = json.dumps(
        {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "waba_1",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "statuses": [
                                    {"id": "wamid.prog.1", "status": "sent", "timestamp": "1732200100"},
                                    {"id": "wamid.prog.1", "status": "sent", "timestamp": "1732200100"},
                                    {"id": "wamid.prog.1", "status": "sent", "timestamp": "1732200105"},
                                    {"id": "wamid.prog.1", "status": "delivered", "timestamp": "1732200110"},
                                    {"id": "wamid.prog.1", "status": "read", "timestamp": "1732200120"},
                                ]
                            },
                        }
                    ],
                }
            ],
        }
    ).encode("utf-8")

    r_batch = api_client.post(
        "/api/webhooks/whatsapp",
        content=batch_body,
        headers={
            "X-Hub-Signature-256": _sign_whatsapp_webhook("meta_seq_secret", batch_body),
            "Content-Type": "application/json",
        },
    )
    assert r_batch.status_code == 200
    # 3 distinct legitimate progressions (`sent`, `delivered`, `read`), 1 duplicate ignored, 1 redundant repeated `sent` ignored
    assert r_batch.json() == {"status": "ok", "processed": 3, "duplicates": 1}

    db.refresh(rec)
    db.refresh(camp)
    assert rec.delivery_status == DeliveryStatus.READ
    assert camp.status == CampaignStatus.COMPLETED

    # Verify stale worker-A completion cannot overwrite active worker-B state via fencing
    from app.services.campaign_worker import ClaimedRecipientJob, _persist_job_outcome

    rec.delivery_status = DeliveryStatus.PROCESSING
    rec.locked_by = "worker-B"
    db.flush()

    stale_job_from_worker_a = ClaimedRecipientJob(
        recipient_id=rec.id,
        worker_id="worker-A",
        channel=MessageChannel.WHATSAPP,
        campaign_id=camp.id,
        customer_id=cust.id,
        attempt_count=1,
        max_attempts=5,
        idempotency_key="k",
        subject=None,
        content="Progression check",
        campaign_name=camp.name,
        approved_template_name="prog_v1",
    )
    _persist_job_outcome(
        db,
        stale_job_from_worker_a,
        {"outcome": "error", "error_code": "stale_err", "retryable": False},
        allow_deferred_retry=True,
    )
    db.refresh(rec)
    # Active worker-B ownership and PROCESSING state preserved untouched!
    assert rec.delivery_status == DeliveryStatus.PROCESSING
    assert rec.locked_by == "worker-B"


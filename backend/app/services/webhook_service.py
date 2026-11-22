"""Secure, idempotent delivery-status webhook processing for Resend (Email) and Meta (WhatsApp)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import log_background_event
from app.models.campaign import CampaignRecipient, MarketingWebhookEvent
from app.models.customer import Customer
from app.models.enums import DeliveryStatus, MessageChannel
from app.services.campaign_worker import recompute_campaign_status

PLACEHOLDER_WEBHOOK_SECRETS = {
    "",
    "whsec_your_resend_webhook_secret_placeholder",
    "your_meta_app_secret_placeholder",
    "your_whatsapp_webhook_verify_token_placeholder",
}

# Rank order for forward-only delivery progress states; terminal outcomes (>= 10) are immutable
# except DELIVERED/READ receiving a subsequent spam suppression (SUPPRESSED).
_PROGRESS_RANK: dict[DeliveryStatus, int] = {
    DeliveryStatus.QUEUED: 0,
    DeliveryStatus.PROCESSING: 0,
    DeliveryStatus.RETRYING: 0,
    DeliveryStatus.UNRESOLVED: 0,
    DeliveryStatus.ACCEPTED: 1,
    DeliveryStatus.SENT: 2,
    DeliveryStatus.DELIVERED: 3,
    DeliveryStatus.READ: 4,
}
_TERMINAL_FAILURE_OR_SKIP = {
    DeliveryStatus.BOUNCED,
    DeliveryStatus.FAILED,
    DeliveryStatus.SUPPRESSED,
    DeliveryStatus.SKIPPED,
}


def can_transition_delivery_status(current: DeliveryStatus, target: DeliveryStatus) -> bool:
    """Enforce strictly valid, out-of-order-safe delivery status transitions."""
    if current == target:
        return False
    if current in _TERMINAL_FAILURE_OR_SKIP:
        # Terminal failure/suppression/skip states cannot be reverted by stale callbacks.
        return False
    if current in (DeliveryStatus.DELIVERED, DeliveryStatus.READ):
        if target == DeliveryStatus.SUPPRESSED:
            return True
        # Out-of-order older `sent`/`accepted`/`bounced`/`failed` cannot downgrade DELIVERED or READ,
        # and READ cannot downgrade to DELIVERED.
        cur_rank = _PROGRESS_RANK.get(current, 0)
        tgt_rank = _PROGRESS_RANK.get(target, -1)
        return tgt_rank > cur_rank
    if target in _TERMINAL_FAILURE_OR_SKIP:
        return True
    cur_rank = _PROGRESS_RANK.get(current, 0)
    tgt_rank = _PROGRESS_RANK.get(target, -1)
    return tgt_rank > cur_rank


def _decode_svix_secret(secret: str) -> bytes:
    cleaned = secret.strip()
    if cleaned.startswith("whsec_"):
        cleaned = cleaned[6:]
        try:
            return base64.b64decode(cleaned)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Resend webhook signing secret format is invalid.",
            ) from exc
    return cleaned.encode("utf-8")


def _verify_resend_svix_signature(
    *,
    raw_body: bytes,
    svix_id: Optional[str],
    svix_timestamp: Optional[str],
    svix_signature: Optional[str],
) -> int:
    secret = (settings.RESEND_WEBHOOK_SECRET or "").strip()
    if secret in PLACEHOLDER_WEBHOOK_SECRETS:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Resend webhook secret is not configured.",
        )

    msg_id = (svix_id or "").strip()
    ts_str = (svix_timestamp or "").strip()
    sig_header = (svix_signature or "").strip()
    if not msg_id or not ts_str or not sig_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Resend webhook signature headers.",
        )

    try:
        ts_val = int(ts_str)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Resend webhook timestamp.",
        ) from exc

    tolerance = max(1, int(settings.WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS or 300))
    if abs(int(time.time()) - ts_val) > tolerance:
        log_background_event(
            "webhook.email_timestamp_out_of_window",
            level=logging.WARNING,
            svix_id=msg_id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Resend webhook timestamp outside permitted tolerance.",
        )

    try:
        raw_text = raw_body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook body must be UTF-8 encoded.",
        ) from exc

    signed_payload = f"{msg_id}.{ts_str}.{raw_text}".encode("utf-8")
    secret_bytes = _decode_svix_secret(secret)
    expected_b64 = base64.b64encode(
        hmac.new(secret_bytes, signed_payload, hashlib.sha256).digest()
    ).decode("utf-8")

    verified = False
    for part in sig_header.split():
        if "," not in part:
            continue
        version, candidate_sig = part.split(",", 1)
        if version.strip() == "v1" and hmac.compare_digest(candidate_sig.strip(), expected_b64):
            verified = True
            break

    if not verified:
        log_background_event(
            "webhook.email_signature_invalid",
            level=logging.WARNING,
            svix_id=msg_id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Resend webhook signature.",
        )
    return ts_val


def _sanitize_webhook_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Retain safe event structure without raw HTML bodies or personal contact tokens."""
    sanitized: dict[str, Any] = {}
    for k, v in payload.items():
        kl = str(k).lower()
        if kl in (
            "html",
            "text",
            "body",
            "authorization",
            "token",
            "secret",
            "email",
            "to",
            "from",
            "subject",
            "recipient_id",
            "phone",
            "phone_number",
            "wa_id",
        ):
            continue
        if isinstance(v, dict):
            sanitized[str(k)] = _sanitize_webhook_payload(v)
        elif isinstance(v, list):
            sanitized[str(k)] = [
                _sanitize_webhook_payload(item) if isinstance(item, dict) else item for item in v[:20]
            ]
        else:
            sanitized[str(k)] = v
    return sanitized


def _apply_status_transition(
    db: Session,
    *,
    recipient: CampaignRecipient,
    target_status: DeliveryStatus,
    failure_reason: Optional[str] = None,
    error_code: Optional[str] = None,
    event_time: Optional[datetime] = None,
) -> str:
    """Apply state transition safely with terminal and out-of-order guards."""
    now = event_time or datetime.now(timezone.utc)
    if not can_transition_delivery_status(recipient.delivery_status, target_status):
        return "ignored_out_of_order"

    was_unresolved = recipient.delivery_status == DeliveryStatus.UNRESOLVED
    recipient.delivery_status = target_status
    if target_status in (DeliveryStatus.SENT, DeliveryStatus.DELIVERED, DeliveryStatus.READ):
        if was_unresolved:
            meta = dict(recipient.provider_response_metadata or {})
            meta["reconciled_from_ambiguous_timeout"] = True
            recipient.provider_response_metadata = meta
            recipient.error_code = None
            recipient.failure_reason = None
    if target_status == DeliveryStatus.SENT:
        recipient.sent_at = recipient.sent_at or now
    elif target_status == DeliveryStatus.DELIVERED:
        recipient.delivered_at = now
    elif target_status == DeliveryStatus.READ:
        recipient.delivered_at = recipient.delivered_at or now
        recipient.read_at = now
    elif target_status == DeliveryStatus.BOUNCED:
        recipient.bounced_at = now
        if failure_reason:
            recipient.failure_reason = failure_reason[:500]
        if error_code:
            recipient.error_code = error_code[:80]
    elif target_status == DeliveryStatus.SUPPRESSED:
        recipient.failed_at = now
        recipient.failure_reason = (failure_reason or "Recipient reported complaint/suppression")[:500]
        recipient.error_code = (error_code or "recipient_suppressed")[:80]
        # Immediately enforce opt-out if recipient suppressed/complained
        if recipient.channel == MessageChannel.EMAIL:
            cust = db.get(Customer, recipient.customer_id)
            if cust and cust.email_marketing_consent:
                cust.email_marketing_consent = False
    elif target_status == DeliveryStatus.FAILED:
        recipient.failed_at = now
        if failure_reason:
            recipient.failure_reason = failure_reason[:500]
        if error_code:
            recipient.error_code = error_code[:80]

    cid = (
        recipient.email_campaign_id
        if recipient.channel == MessageChannel.EMAIL
        else recipient.whatsapp_campaign_id
    )
    if cid:
        recompute_campaign_status(db, recipient.channel, cid)

    db.flush()
    return "processed"


def process_email_webhook(
    db: Session,
    *,
    raw_body: bytes,
    svix_id: Optional[str],
    svix_timestamp: Optional[str],
    svix_signature: Optional[str],
) -> dict[str, Any]:
    if len(raw_body) > int(settings.MAX_WEBHOOK_PAYLOAD_BYTES):
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Webhook payload exceeds maximum permitted size.",
        )

    _verify_resend_svix_signature(
        raw_body=raw_body,
        svix_id=svix_id,
        svix_timestamp=svix_timestamp,
        svix_signature=svix_signature,
    )

    try:
        parsed = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed email webhook JSON payload.",
        ) from exc

    if not isinstance(parsed, dict) or not parsed.get("type") or not isinstance(parsed.get("data"), dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Resend webhook payload structure.",
        )

    event_id = (svix_id or "").strip()
    event_type = str(parsed["type"]).strip().lower()
    data = parsed["data"]
    provider_message_id = str(data.get("email_id") or "").strip() or None

    # Idempotency registration in savepoint
    evt_row = MarketingWebhookEvent(
        provider="resend",
        event_id=event_id,
        event_type=event_type,
        provider_message_id=provider_message_id,
        processing_status="processed",
        payload=_sanitize_webhook_payload(parsed),
    )
    try:
        with db.begin_nested():
            db.add(evt_row)
            db.flush()
    except IntegrityError:
        return {"status": "duplicate_ignored"}

    if not provider_message_id:
        evt_row.processing_status = "unmatched_recipient"
        db.flush()
        return {"status": "ok", "processed": 0, "duplicates": 0}

    rec = db.scalar(
        select(CampaignRecipient)
        .where(
            CampaignRecipient.channel == MessageChannel.EMAIL,
            CampaignRecipient.provider_message_id == provider_message_id,
        )
        .with_for_update()
    )
    if not rec:
        evt_row.processing_status = "unmatched_recipient"
        db.flush()
        return {"status": "ok", "processed": 0, "duplicates": 0}

    evt_row.campaign_recipient_id = rec.id

    event_map: dict[str, DeliveryStatus] = {
        "email.sent": DeliveryStatus.SENT,
        "email.delivered": DeliveryStatus.DELIVERED,
        "email.bounced": DeliveryStatus.BOUNCED,
        "email.complained": DeliveryStatus.SUPPRESSED,
        "email.failed": DeliveryStatus.FAILED,
    }
    target = event_map.get(event_type)
    if target is None:
        # e.g. email.delivery_delayed: keep state, note event safely
        evt_row.processing_status = "noted_non_terminal"
        db.flush()
        return {"status": "ok", "processed": 0, "duplicates": 0}

    bounce_info = data.get("bounce") if isinstance(data.get("bounce"), dict) else {}
    reason = bounce_info.get("message") or data.get("reason")
    outcome = _apply_status_transition(
        db,
        recipient=rec,
        target_status=target,
        failure_reason=str(reason) if reason else None,
        error_code=event_type.replace(".", "_"),
    )
    evt_row.processing_status = outcome
    db.flush()
    return {"status": "ok", "processed": 1 if outcome == "processed" else 0, "duplicates": 0}


def verify_whatsapp_webhook_challenge(
    *,
    hub_mode: Optional[str],
    hub_verify_token: Optional[str],
    hub_challenge: Optional[str],
) -> str:
    configured = (settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN or "").strip()
    if configured in PLACEHOLDER_WEBHOOK_SECRETS:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp webhook verify token is not configured.",
        )
    if (
        (hub_mode or "").strip() != "subscribe"
        or not hub_verify_token
        or not hmac.compare_digest(hub_verify_token.strip(), configured)
        or not hub_challenge
    ):
        log_background_event("webhook.whatsapp_verify_failed", level=logging.WARNING)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="WhatsApp webhook verification failed.",
        )
    return hub_challenge


def _verify_whatsapp_signature(raw_body: bytes, signature_header: Optional[str]) -> None:
    secret = (settings.WHATSAPP_APP_SECRET or "").strip()
    if secret in PLACEHOLDER_WEBHOOK_SECRETS:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp app secret is not configured.",
        )
    sig = (signature_header or "").strip()
    if not sig.startswith("sha256="):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed WhatsApp webhook signature.",
        )
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    provided = sig[7:].strip().lower()
    if not hmac.compare_digest(expected, provided):
        log_background_event("webhook.whatsapp_signature_invalid", level=logging.WARNING)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid WhatsApp webhook signature.",
        )


def process_whatsapp_webhook(
    db: Session,
    *,
    raw_body: bytes,
    signature_header: Optional[str],
) -> dict[str, Any]:
    if len(raw_body) > int(settings.MAX_WEBHOOK_PAYLOAD_BYTES):
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Webhook payload exceeds maximum permitted size.",
        )

    _verify_whatsapp_signature(raw_body=raw_body, signature_header=signature_header)

    try:
        parsed = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed WhatsApp webhook JSON payload.",
        ) from exc

    if not isinstance(parsed, dict) or not isinstance(parsed.get("entry"), list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid WhatsApp webhook payload structure.",
        )

    status_map: dict[str, DeliveryStatus] = {
        "sent": DeliveryStatus.SENT,
        "delivered": DeliveryStatus.DELIVERED,
        "read": DeliveryStatus.READ,
        "failed": DeliveryStatus.FAILED,
    }

    processed = 0
    duplicates = 0

    for entry in parsed.get("entry", []):
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes", []) if isinstance(entry.get("changes"), list) else []:
            if not isinstance(change, dict):
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            for st in value.get("statuses", []) if isinstance(value.get("statuses"), list) else []:
                if not isinstance(st, dict):
                    continue
                wamid = str(st.get("id") or "").strip()
                wa_status = str(st.get("status") or "").strip().lower()
                ts_raw = str(st.get("timestamp") or "").strip()
                if not wamid or wa_status not in status_map:
                    continue

                digest_fallback = hashlib.sha256(
                    json.dumps(st, sort_keys=True).encode("utf-8")
                ).hexdigest()[:16]
                event_id = f"{wamid}:{wa_status}:{ts_raw or digest_fallback}"

                evt_row = MarketingWebhookEvent(
                    provider="whatsapp",
                    event_id=event_id[:180],
                    event_type=f"whatsapp.{wa_status}",
                    provider_message_id=wamid[:150],
                    processing_status="processed",
                    payload=_sanitize_webhook_payload(st),
                )
                try:
                    with db.begin_nested():
                        db.add(evt_row)
                        db.flush()
                except IntegrityError:
                    duplicates += 1
                    continue

                rec = db.scalar(
                    select(CampaignRecipient)
                    .where(
                        CampaignRecipient.channel == MessageChannel.WHATSAPP,
                        CampaignRecipient.provider_message_id == wamid,
                    )
                    .with_for_update()
                )
                if not rec:
                    # Fallback reconciliation for UNRESOLVED post-submission ReadTimeout rows:
                    # match Meta `statuses[].recipient_id` against Customer.phone_number when
                    # `provider_message_id` was not captured during the timed-out HTTP response.
                    raw_recipient_id = str(st.get("recipient_id") or "").strip()
                    if raw_recipient_id:
                        normalized_e164 = (
                            raw_recipient_id if raw_recipient_id.startswith("+") else f"+{raw_recipient_id}"
                        )
                        rec = db.scalar(
                            select(CampaignRecipient)
                            .join(Customer, Customer.id == CampaignRecipient.customer_id)
                            .where(
                                CampaignRecipient.channel == MessageChannel.WHATSAPP,
                                CampaignRecipient.delivery_status == DeliveryStatus.UNRESOLVED,
                                CampaignRecipient.provider_message_id.is_(None),
                                Customer.phone_number.in_((normalized_e164, raw_recipient_id)),
                            )
                            .order_by(CampaignRecipient.updated_at.desc())
                            .limit(1)
                            .with_for_update(of=CampaignRecipient)
                        )
                        if rec:
                            rec.provider_message_id = wamid[:150]
                if not rec:
                    evt_row.processing_status = "unmatched_recipient"
                    db.flush()
                    continue

                evt_row.campaign_recipient_id = rec.id
                errors_list = st.get("errors") if isinstance(st.get("errors"), list) else []
                err_code = None
                err_reason = None
                if errors_list and isinstance(errors_list[0], dict):
                    err_code = str(errors_list[0].get("code") or "whatsapp_failed")
                    err_reason = str(errors_list[0].get("title") or errors_list[0].get("message") or "")

                event_dt: Optional[datetime] = None
                if ts_raw.isdigit():
                    event_dt = datetime.fromtimestamp(int(ts_raw), tz=timezone.utc)

                outcome = _apply_status_transition(
                    db,
                    recipient=rec,
                    target_status=status_map[wa_status],
                    failure_reason=err_reason or None,
                    error_code=err_code,
                    event_time=event_dt,
                )
                evt_row.processing_status = outcome
                db.flush()
                if outcome == "processed":
                    processed += 1

    return {"status": "ok", "processed": processed, "duplicates": duplicates}

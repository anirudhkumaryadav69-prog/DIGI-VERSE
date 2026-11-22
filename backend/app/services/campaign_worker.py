"""Persistent background campaign processing engine and worker execution cycle.

Architecture highlights:
- Multi-worker safe: uses PostgreSQL `SELECT ... FOR UPDATE SKIP LOCKED` in short transactions.
- Lock isolation: commits row-claim state (`processing`) BEFORE making external HTTP requests,
  so PostgreSQL row locks are never held across slow network I/O.
- Crash & restart recovery: stale `processing` locks (`locked_at < now - stale_seconds`) are
  reclaimed safely back into `retrying` or terminal `failed` if retry budget is exhausted.
- Live consent & opt-out guard: re-validates customer status and marketing consent right before
  calling external providers; unsubscribed recipients transition to `skipped`.
- Bounded exponential backoff with HTTP `429 Retry-After` support and provider idempotency handling.
"""
from __future__ import annotations

import logging
import socket
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import log_background_event
from app.models.campaign import (
    CampaignRecipient,
    EmailCampaign,
    WhatsAppCampaign,
    WorkerHeartbeat,
)
from app.models.customer import Customer
from app.models.enums import AccountStatus, CampaignStatus, DeliveryStatus, MessageChannel
from app.services.email_service import (
    EMAIL_FORMAT_RE,
    EmailDeliveryError,
    get_email_provider,
)
from app.services.whatsapp_service import (
    E164_PHONE_RE,
    WhatsAppDeliveryError,
    get_whatsapp_provider,
)

DISPATCHED_DELIVERY_STATUSES = (
    DeliveryStatus.ACCEPTED,
    DeliveryStatus.SENT,
    DeliveryStatus.DELIVERED,
    DeliveryStatus.READ,
)
CONFIRMED_DELIVERED_STATUSES = (
    DeliveryStatus.DELIVERED,
    DeliveryStatus.READ,
)
IN_FLIGHT_DELIVERY_STATUSES = (
    DeliveryStatus.QUEUED,
    DeliveryStatus.PROCESSING,
    DeliveryStatus.RETRYING,
    DeliveryStatus.ACCEPTED,
    DeliveryStatus.SENT,
    DeliveryStatus.UNRESOLVED,
)
TERMINAL_FAILURE_DELIVERY_STATUSES = (
    DeliveryStatus.FAILED,
    DeliveryStatus.BOUNCED,
    DeliveryStatus.SUPPRESSED,
)
ACTIVE_CAMPAIGN_PROCESSING_STATUSES = (
    CampaignStatus.SCHEDULED,
    CampaignStatus.QUEUED,
    CampaignStatus.SENDING,
    CampaignStatus.PROCESSING,
)


@dataclass
class ClaimedRecipientJob:
    recipient_id: uuid.UUID
    worker_id: str
    channel: MessageChannel
    campaign_id: uuid.UUID
    customer_id: uuid.UUID
    attempt_count: int
    max_attempts: int
    idempotency_key: str
    subject: Optional[str]
    content: str
    campaign_name: str
    approved_template_name: Optional[str]


def make_recipient_idempotency_key(
    channel: MessageChannel,
    campaign_id: uuid.UUID,
    customer_id: uuid.UUID,
    generation: int = 1,
) -> str:
    """Return a deterministic provider idempotency key for a campaign recipient send."""
    prefix = f"dv-{channel.value}-{campaign_id.hex[:12]}-{customer_id.hex[:12]}-g{generation}"
    return prefix[:120]


def calculate_backoff_seconds(attempt_count: int, retry_after_seconds: Optional[int] = None) -> int:
    base = max(1, int(settings.CAMPAIGN_RETRY_BASE_SECONDS or 30))
    cap = max(base, int(settings.CAMPAIGN_RETRY_MAX_BACKOFF_SECONDS or 1800))
    exp_delay = min(cap, base * (2 ** max(0, attempt_count - 1)))
    if retry_after_seconds is not None and retry_after_seconds > 0:
        return min(cap, max(exp_delay, int(retry_after_seconds)))
    return int(exp_delay)


def _eligible_customers_for_campaign(
    db: Session,
    channel: MessageChannel,
    audience_criteria: Optional[dict[str, Any]],
) -> list[Customer]:
    conds = [Customer.account_status == AccountStatus.ACTIVE]
    if channel == MessageChannel.EMAIL:
        conds.append(Customer.email_marketing_consent.is_(True))
    else:
        conds.append(Customer.whatsapp_marketing_consent.is_(True))
        conds.append(Customer.phone_number.is_not(None))

    criteria = audience_criteria or {}
    if criteria.get("verified_phone_only"):
        conds.append(Customer.is_phone_verified.is_(True))
    if criteria.get("verified_email_only"):
        conds.append(Customer.is_email_verified.is_(True))

    return list(db.scalars(select(Customer).where(*conds).order_by(Customer.created_at.asc())).all())


def materialize_campaign_recipients(
    db: Session,
    channel: MessageChannel,
    campaign: EmailCampaign | WhatsAppCampaign,
    *,
    force_new_generation: bool = False,
) -> int:
    """Resolve consented customers and persist missing `CampaignRecipient` jobs idempotently."""
    eligible = _eligible_customers_for_campaign(db, channel, campaign.audience_criteria)
    existing_rows = db.scalars(
        select(CampaignRecipient).where(
            CampaignRecipient.email_campaign_id == campaign.id
            if channel == MessageChannel.EMAIL
            else CampaignRecipient.whatsapp_campaign_id == campaign.id
        )
    ).all()
    existing_by_customer = {r.customer_id: r for r in existing_rows}

    created_or_reset = 0
    max_attempts = max(1, int(settings.CAMPAIGN_MAX_RETRY_ATTEMPTS or 5))
    for cust in eligible:
        existing = existing_by_customer.get(cust.id)
        if existing:
            if force_new_generation and existing.delivery_status in (
                DeliveryStatus.FAILED,
                DeliveryStatus.SKIPPED,
            ):
                existing.delivery_status = DeliveryStatus.QUEUED
                existing.attempt_count = 0
                existing.max_attempts = max_attempts
                existing.next_retry_at = None
                existing.locked_by = None
                existing.locked_at = None
                existing.failure_reason = None
                existing.error_code = None
                existing.is_retryable_error = None
                existing.failed_at = None
                existing.idempotency_key = (
                    f"dv-{channel.value}-{campaign.id.hex[:12]}-{cust.id.hex[:12]}-{uuid.uuid4().hex[:6]}"
                )
                created_or_reset += 1
            continue

        values: dict[str, Any] = {
            "channel": channel.value,
            "customer_id": cust.id,
            "delivery_status": DeliveryStatus.QUEUED.value,
            "idempotency_key": make_recipient_idempotency_key(channel, campaign.id, cust.id),
            "attempt_count": 0,
            "max_attempts": max_attempts,
        }
        if channel == MessageChannel.EMAIL:
            values["email_campaign_id"] = campaign.id
            conflict_cols = ["email_campaign_id", "customer_id"]
        else:
            values["whatsapp_campaign_id"] = campaign.id
            conflict_cols = ["whatsapp_campaign_id", "customer_id"]

        stmt = (
            pg_insert(CampaignRecipient)
            .values(**values)
            .on_conflict_do_nothing(index_elements=conflict_cols)
        )
        res = db.execute(stmt)
        if res.rowcount:
            created_or_reset += res.rowcount

    db.flush()
    return created_or_reset


def recompute_campaign_status(
    db: Session,
    channel: MessageChannel,
    campaign_id: uuid.UUID,
) -> Optional[EmailCampaign | WhatsAppCampaign]:
    """Recompute parent campaign aggregate status solely from persisted recipient states."""
    db.flush()
    model = EmailCampaign if channel == MessageChannel.EMAIL else WhatsAppCampaign
    fk_col = (
        CampaignRecipient.email_campaign_id
        if channel == MessageChannel.EMAIL
        else CampaignRecipient.whatsapp_campaign_id
    )
    camp = db.scalar(select(model).where(model.id == campaign_id).with_for_update())
    if not camp:
        return None
    if camp.status == CampaignStatus.CANCELLED:
        return camp

    counts_rows = db.execute(
        select(CampaignRecipient.delivery_status, func.count(CampaignRecipient.id))
        .where(fk_col == campaign_id)
        .group_by(CampaignRecipient.delivery_status)
    ).all()
    counts = {status_val: int(cnt) for status_val, cnt in counts_rows}

    in_flight = sum(counts.get(s, 0) for s in IN_FLIGHT_DELIVERY_STATUSES)
    confirmed_delivered = sum(counts.get(s, 0) for s in CONFIRMED_DELIVERED_STATUSES)
    failed = sum(counts.get(s, 0) for s in TERMINAL_FAILURE_DELIVERY_STATUSES)
    total = sum(counts.values())

    now = datetime.now(timezone.utc)
    if total == 0:
        if camp.status in (CampaignStatus.QUEUED, CampaignStatus.PROCESSING, CampaignStatus.SENDING):
            camp.status = CampaignStatus.COMPLETED
            camp.completed_at = camp.completed_at or now
            camp.locked_by = None
            camp.locked_at = None
    elif in_flight > 0:
        camp.status = CampaignStatus.PROCESSING
        camp.completed_at = None
    elif failed > 0 and confirmed_delivered > 0:
        camp.status = CampaignStatus.PARTIALLY_COMPLETED
        camp.completed_at = camp.completed_at or now
        camp.locked_by = None
        camp.locked_at = None
    elif failed > 0 and confirmed_delivered == 0:
        camp.status = CampaignStatus.FAILED
        camp.completed_at = None
        camp.locked_by = None
        camp.locked_at = None
    else:
        camp.status = CampaignStatus.COMPLETED
        camp.completed_at = camp.completed_at or now
        camp.locked_by = None
        camp.locked_at = None

    db.flush()
    return camp


def claim_and_enqueue_due_campaigns(
    db: Session,
    *,
    worker_id: str,
    max_campaigns: int = 10,
) -> dict[str, int]:
    """Claim due `SCHEDULED` campaigns using `FOR UPDATE SKIP LOCKED` and enqueue recipient jobs."""
    now = datetime.now(timezone.utc)
    enqueued_email = 0
    enqueued_wa = 0

    for channel, model in (
        (MessageChannel.EMAIL, EmailCampaign),
        (MessageChannel.WHATSAPP, WhatsAppCampaign),
    ):
        campaigns = db.scalars(
            select(model)
            .where(
                model.status == CampaignStatus.SCHEDULED,
                or_(model.scheduled_for.is_(None), model.scheduled_for <= now),
            )
            .order_by(model.created_at.asc())
            .limit(max_campaigns)
            .with_for_update(skip_locked=True)
        ).all()

        for camp in campaigns:
            camp.status = CampaignStatus.QUEUED
            camp.queued_at = camp.queued_at or now
            camp.started_at = camp.started_at or now
            camp.locked_by = worker_id
            camp.locked_at = now
            camp.last_error = None
            materialize_campaign_recipients(db, channel, camp)
            recompute_campaign_status(db, channel, camp.id)
            if channel == MessageChannel.EMAIL:
                enqueued_email += 1
            else:
                enqueued_wa += 1

    db.flush()
    return {"email_campaigns": enqueued_email, "whatsapp_campaigns": enqueued_wa}


def recover_stale_locks(
    db: Session,
    *,
    stale_seconds: Optional[int] = None,
) -> dict[str, int]:
    """Reclaim orphaned `processing` recipient jobs and stale campaign locks after worker crashes."""
    ttl = max(1, int(stale_seconds if stale_seconds is not None else settings.CAMPAIGN_WORKER_STALE_LOCK_SECONDS))
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=ttl)
    now = datetime.now(timezone.utc)

    stale_recipients = db.scalars(
        select(CampaignRecipient)
        .where(
            CampaignRecipient.delivery_status == DeliveryStatus.PROCESSING,
            or_(CampaignRecipient.locked_at.is_(None), CampaignRecipient.locked_at < cutoff),
        )
        .with_for_update(skip_locked=True)
    ).all()

    requeued = 0
    exhausted = 0
    touched_campaigns: set[tuple[MessageChannel, uuid.UUID]] = set()

    for rec in stale_recipients:
        rec.locked_by = None
        rec.locked_at = None
        if rec.attempt_count >= rec.max_attempts:
            rec.delivery_status = DeliveryStatus.FAILED
            rec.failed_at = now
            rec.error_code = "stale_lock_exhausted"
            rec.is_retryable_error = False
            rec.failure_reason = "Worker lock expired after reaching maximum retry attempts."
            exhausted += 1
        else:
            rec.delivery_status = DeliveryStatus.RETRYING
            rec.next_retry_at = now
            rec.error_code = "stale_lock_recovered"
            rec.is_retryable_error = True
            rec.failure_reason = "Recovered stale processing lock after worker interruption."
            requeued += 1

        cid = rec.email_campaign_id if rec.channel == MessageChannel.EMAIL else rec.whatsapp_campaign_id
        if cid:
            touched_campaigns.add((rec.channel, cid))

    # Reclaim stale campaign-level queue locks so campaigns never remain stranded
    stale_campaigns_recovered = 0
    for channel, model in (
        (MessageChannel.EMAIL, EmailCampaign),
        (MessageChannel.WHATSAPP, WhatsAppCampaign),
    ):
        stale_camps = db.scalars(
            select(model)
            .where(
                model.status.in_((CampaignStatus.QUEUED, CampaignStatus.SENDING)),
                model.locked_at.is_not(None),
                model.locked_at < cutoff,
            )
            .with_for_update(skip_locked=True)
        ).all()
        for camp in stale_camps:
            camp.locked_by = None
            camp.locked_at = None
            touched_campaigns.add((channel, camp.id))
            stale_campaigns_recovered += 1

    for channel, cid in touched_campaigns:
        recompute_campaign_status(db, channel, cid)

    if requeued or exhausted or stale_campaigns_recovered:
        log_background_event(
            "worker.stale_jobs_recovered",
            level=logging.WARNING,
            requeued=requeued,
            exhausted=exhausted,
            stale_campaigns=stale_campaigns_recovered,
        )
    db.flush()
    return {"requeued": requeued, "exhausted": exhausted, "stale_campaigns": stale_campaigns_recovered}


def claim_recipient_batch(
    db: Session,
    *,
    worker_id: str,
    batch_size: int = 50,
    campaign_filter: Optional[tuple[MessageChannel, uuid.UUID]] = None,
) -> list[ClaimedRecipientJob]:
    """Atomically claim `queued`/`retrying` recipient rows using PostgreSQL `SKIP LOCKED`."""
    now = datetime.now(timezone.utc)
    conds = [
        CampaignRecipient.delivery_status.in_((DeliveryStatus.QUEUED, DeliveryStatus.RETRYING)),
        or_(CampaignRecipient.next_retry_at.is_(None), CampaignRecipient.next_retry_at <= now),
    ]
    if campaign_filter is not None:
        ch, cid = campaign_filter
        if ch == MessageChannel.EMAIL:
            conds.append(CampaignRecipient.email_campaign_id == cid)
        else:
            conds.append(CampaignRecipient.whatsapp_campaign_id == cid)

    rows = db.scalars(
        select(CampaignRecipient)
        .where(*conds)
        .order_by(CampaignRecipient.next_retry_at.asc().nullsfirst(), CampaignRecipient.id.asc())
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    ).all()

    claimed: list[ClaimedRecipientJob] = []
    for rec in rows:
        if rec.channel == MessageChannel.EMAIL:
            camp = db.get(EmailCampaign, rec.email_campaign_id)
            if not camp or camp.status not in ACTIVE_CAMPAIGN_PROCESSING_STATUSES:
                if camp and camp.status == CampaignStatus.CANCELLED:
                    rec.delivery_status = DeliveryStatus.SKIPPED
                    rec.failure_reason = "Campaign was cancelled before delivery."
                continue
            camp_name = camp.name
            subject = camp.subject
            content = camp.content
            approved_tpl = None
            cid = camp.id
        else:
            camp = db.get(WhatsAppCampaign, rec.whatsapp_campaign_id)
            if not camp or camp.status not in ACTIVE_CAMPAIGN_PROCESSING_STATUSES:
                if camp and camp.status == CampaignStatus.CANCELLED:
                    rec.delivery_status = DeliveryStatus.SKIPPED
                    rec.failure_reason = "Campaign was cancelled before delivery."
                continue
            camp_name = camp.name
            subject = None
            content = camp.content
            approved_tpl = camp.approved_template_name
            cid = camp.id

        if not rec.idempotency_key:
            rec.idempotency_key = make_recipient_idempotency_key(rec.channel, cid, rec.customer_id)

        rec.delivery_status = DeliveryStatus.PROCESSING
        rec.attempt_count = rec.attempt_count + 1
        rec.locked_by = worker_id
        rec.locked_at = now
        rec.next_retry_at = None

        claimed.append(
            ClaimedRecipientJob(
                recipient_id=rec.id,
                worker_id=worker_id,
                channel=rec.channel,
                campaign_id=cid,
                customer_id=rec.customer_id,
                attempt_count=rec.attempt_count,
                max_attempts=rec.max_attempts,
                idempotency_key=rec.idempotency_key,
                subject=subject,
                content=content,
                campaign_name=camp_name,
                approved_template_name=approved_tpl,
            )
        )

    db.flush()
    return claimed


def _check_live_recipient_consent(
    db: Session,
    channel: MessageChannel,
    customer_id: uuid.UUID,
) -> tuple[bool, Optional[Customer], Optional[str]]:
    cust = db.get(Customer, customer_id)
    if not cust:
        return False, None, "Customer account no longer exists."
    if cust.account_status != AccountStatus.ACTIVE:
        return False, cust, f"Customer account is not active ({cust.account_status.value})."
    if channel == MessageChannel.EMAIL:
        if not cust.email_marketing_consent:
            return False, cust, "Customer unsubscribed from email marketing before dispatch."
        if not cust.email or not EMAIL_FORMAT_RE.match(cust.email.strip()):
            return False, cust, "Customer has no valid email address."
    else:
        if not cust.whatsapp_marketing_consent:
            return False, cust, "Customer opted out of WhatsApp marketing before dispatch."
        if not cust.phone_number or not E164_PHONE_RE.match(cust.phone_number.strip()):
            return False, cust, "Customer has no valid E.164 phone number."
    return True, cust, None


def _execute_provider_send(
    job: ClaimedRecipientJob,
    customer: Customer,
) -> dict[str, Any]:
    """Execute external provider HTTP call outside any database row lock."""
    metadata = {"campaign_id": str(job.campaign_id), "customer_id": str(job.customer_id)}
    try:
        if job.channel == MessageChannel.EMAIL:
            provider = get_email_provider()
            msg_id = provider.send_transactional_email(
                email=customer.email,
                template_name=f"campaign:{job.campaign_name}",
                subject=job.subject or job.campaign_name,
                body=job.content,
                metadata=metadata,
                category="marketing",
                idempotency_key=job.idempotency_key,
            )
            return {
                "outcome": "accepted",
                "provider_message_id": msg_id,
                "provider_metadata": {"provider": "email", "idempotency_supported": True},
            }
        else:
            provider = get_whatsapp_provider()
            msg_id = provider.send_template_message(
                phone_number=customer.phone_number or "",
                approved_template_name=job.approved_template_name or "",
                content=job.content,
                metadata=metadata,
                idempotency_key=job.idempotency_key,
            )
            return {
                "outcome": "accepted",
                "provider_message_id": msg_id,
                "provider_metadata": {"provider": "whatsapp", "idempotency_supported": False},
            }
    except EmailDeliveryError as exc:
        return {
            "outcome": "error",
            "error_message": str(exc)[:400] or exc.__class__.__name__,
            "error_code": exc.code,
            "retryable": exc.retryable,
            "retry_after_seconds": exc.retry_after_seconds,
            "provider_metadata": exc.response_metadata,
        }
    except WhatsAppDeliveryError as exc:
        return {
            "outcome": "error",
            "error_message": str(exc)[:400] or exc.__class__.__name__,
            "error_code": exc.code,
            "retryable": exc.retryable,
            "retry_after_seconds": exc.retry_after_seconds,
            "is_ambiguous_timeout": exc.is_ambiguous_timeout,
            "provider_metadata": exc.response_metadata,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "outcome": "error",
            "error_message": str(exc)[:400] or exc.__class__.__name__,
            "error_code": "unexpected_provider_error",
            "retryable": True,
            "retry_after_seconds": None,
            "provider_metadata": {},
        }


def _persist_job_outcome(
    db: Session,
    job: ClaimedRecipientJob,
    result: dict[str, Any],
    *,
    allow_deferred_retry: bool = True,
) -> None:
    """Persist outcome of a single recipient send inside a short transaction."""
    rec = db.scalar(
        select(CampaignRecipient).where(CampaignRecipient.id == job.recipient_id).with_for_update()
    )
    if not rec:
        return

    # Fencing check: if a stale-lock reaper reclaimed this row for another worker, ignore late write.
    if rec.delivery_status != DeliveryStatus.PROCESSING or (
        rec.locked_by is not None and rec.locked_by != job.worker_id
    ):
        log_background_event(
            "worker.fenced_completion_ignored",
            level=logging.WARNING,
            recipient_id=str(rec.id),
            expected_worker=job.worker_id,
            current_status=rec.delivery_status.value,
        )
        return

    now = datetime.now(timezone.utc)
    rec.locked_by = None
    rec.locked_at = None
    outcome = result["outcome"]

    if outcome == "skipped":
        rec.delivery_status = DeliveryStatus.SKIPPED
        rec.failure_reason = result.get("reason")
        rec.error_code = "consent_or_validation_skipped"
        rec.is_retryable_error = False
        rec.next_retry_at = None
    elif outcome == "accepted":
        rec.delivery_status = DeliveryStatus.ACCEPTED
        rec.provider_message_id = result["provider_message_id"]
        rec.accepted_at = now
        rec.sent_at = now
        rec.failure_reason = None
        rec.error_code = None
        rec.is_retryable_error = False
        rec.next_retry_at = None
        rec.provider_response_metadata = result.get("provider_metadata")
    else:
        is_ambiguous_timeout = bool(result.get("is_ambiguous_timeout", False))
        retryable = bool(result.get("retryable", False))
        can_retry = (
            allow_deferred_retry
            and retryable
            and not is_ambiguous_timeout
            and (rec.attempt_count < rec.max_attempts)
        )
        rec.error_code = result.get("error_code") or "provider_error"
        rec.is_retryable_error = retryable
        rec.failure_reason = result.get("error_message") or "Provider delivery failed."
        rec.provider_response_metadata = result.get("provider_metadata")

        if is_ambiguous_timeout:
            # Post-submission timeout on a provider without idempotency keys:
            # do not blindly retry; mark UNRESOLVED so admins see it and webhooks can reconcile.
            rec.delivery_status = DeliveryStatus.UNRESOLVED
            rec.next_retry_at = None
            rec.failed_at = None
        elif can_retry:
            delay_s = calculate_backoff_seconds(
                rec.attempt_count, retry_after_seconds=result.get("retry_after_seconds")
            )
            rec.delivery_status = DeliveryStatus.RETRYING
            rec.next_retry_at = now + timedelta(seconds=delay_s)
        else:
            rec.delivery_status = DeliveryStatus.FAILED
            rec.failed_at = now
            rec.next_retry_at = None

    recompute_campaign_status(db, job.channel, job.campaign_id)
    db.flush()


def record_worker_heartbeat(
    db: Session,
    *,
    worker_id: str,
    status_str: str = "running",
    processed_increment: int = 0,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    now = datetime.now(timezone.utc)
    hb = db.get(WorkerHeartbeat, worker_id)
    if not hb:
        import os

        hb = WorkerHeartbeat(
            worker_id=worker_id,
            hostname=socket.gethostname()[:150],
            pid=os.getpid(),
            status=status_str,
            started_at=now,
            last_heartbeat_at=now,
            processed_jobs_count=processed_increment,
            metadata_json=metadata,
        )
        db.add(hb)
    else:
        hb.status = status_str
        hb.last_heartbeat_at = now
        hb.processed_jobs_count = int(hb.processed_jobs_count or 0) + processed_increment
        if metadata is not None:
            hb.metadata_json = metadata
    db.flush()


def run_worker_cycle(
    session_factory: sessionmaker[Session] | Callable[[], Session] = SessionLocal,
    *,
    worker_id: Optional[str] = None,
    max_campaigns: int = 10,
    batch_size: Optional[int] = None,
    stale_seconds: Optional[int] = None,
) -> dict[str, int]:
    """Execute one complete persistent worker cycle with strict transaction/lock boundaries."""
    wid = worker_id or f"{socket.gethostname()[:40]}-{uuid.uuid4().hex[:8]}"
    effective_batch = max(1, int(batch_size or settings.CAMPAIGN_WORKER_BATCH_SIZE or 50))

    # Step 1 (short TX): Heartbeat, stale lock recovery, claim due scheduled campaigns, claim batch
    with session_factory() as db:
        record_worker_heartbeat(db, worker_id=wid, status_str="running")
        recovery_stats = recover_stale_locks(db, stale_seconds=stale_seconds)
        enqueued_stats = claim_and_enqueue_due_campaigns(db, worker_id=wid, max_campaigns=max_campaigns)
        jobs = claim_recipient_batch(db, worker_id=wid, batch_size=effective_batch)
        db.commit()

    accepted_count = 0
    retrying_count = 0
    failed_count = 0
    skipped_count = 0

    # Step 2: Process each claimed job WITHOUT holding DB locks during external provider HTTP I/O
    for job in jobs:
        with session_factory() as db:
            consent_ok, cust, skip_reason = _check_live_recipient_consent(
                db, job.channel, job.customer_id
            )

        if not consent_ok or cust is None:
            result: dict[str, Any] = {
                "outcome": "skipped",
                "reason": skip_reason or "Customer not eligible.",
            }
        else:
            result = _execute_provider_send(job, cust)

        with session_factory() as db:
            _persist_job_outcome(db, job, result, allow_deferred_retry=True)
            db.commit()

        if result["outcome"] == "skipped":
            skipped_count += 1
        elif result["outcome"] == "accepted":
            accepted_count += 1
        else:
            if result.get("retryable") and job.attempt_count < job.max_attempts:
                retrying_count += 1
            else:
                failed_count += 1

    # Step 3: Update heartbeat job counter
    if jobs:
        with session_factory() as db:
            record_worker_heartbeat(db, worker_id=wid, status_str="idle", processed_increment=len(jobs))
            db.commit()

    return {
        "email_campaigns": enqueued_stats["email_campaigns"],
        "whatsapp_campaigns": enqueued_stats["whatsapp_campaigns"],
        "claimed_jobs": len(jobs),
        "accepted": accepted_count,
        "retrying": retrying_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "stale_requeued": recovery_stats["requeued"],
        "stale_exhausted": recovery_stats["exhausted"],
    }


def process_campaigns_in_session(
    db: Session,
    *,
    worker_id: str = "in-session-worker",
    max_campaigns: int = 10,
    max_jobs: int = 500,
    allow_deferred_retry: bool = False,
) -> dict[str, int]:
    """Process scheduled/queued campaigns inside a caller-managed Session (e.g. pytest rolled-back tx)."""
    recover_stale_locks(db)
    enqueued = claim_and_enqueue_due_campaigns(db, worker_id=worker_id, max_campaigns=max_campaigns)
    jobs = claim_recipient_batch(db, worker_id=worker_id, batch_size=max_jobs)

    accepted_count = 0
    retrying_count = 0
    failed_count = 0
    skipped_count = 0

    for job in jobs:
        consent_ok, cust, skip_reason = _check_live_recipient_consent(db, job.channel, job.customer_id)
        if not consent_ok or cust is None:
            result: dict[str, Any] = {"outcome": "skipped", "reason": skip_reason}
            skipped_count += 1
        else:
            result = _execute_provider_send(job, cust)
            if result["outcome"] == "accepted":
                accepted_count += 1
            elif allow_deferred_retry and result.get("retryable") and job.attempt_count < job.max_attempts:
                retrying_count += 1
            else:
                failed_count += 1
        _persist_job_outcome(db, job, result, allow_deferred_retry=allow_deferred_retry)

    return {
        "email_campaigns": enqueued["email_campaigns"],
        "whatsapp_campaigns": enqueued["whatsapp_campaigns"],
        "claimed_jobs": len(jobs),
        "accepted": accepted_count,
        "retrying": retrying_count,
        "failed": failed_count,
        "skipped": skipped_count,
    }

# DIGI-VERSE Phase 8.2 — Persistent Campaign Workers, Delivery & Webhooks

## 1. Architecture Overview

Phase 8.2 decouples marketing campaign delivery from FastAPI HTTP request lifecycles using PostgreSQL-backed persistent job queues and a standalone background worker process:

1. **Admin Queueing & Scheduling**:
   - `POST /api/admin/campaigns/{channel}/{id}/schedule`: transitions a campaign to `SCHEDULED` with an optional `scheduled_for` UTC timestamp.
   - `POST /api/admin/campaigns/{channel}/{id}/queue`: transitions a campaign to `QUEUED`, resolves eligible consented customers, and materializes persistent `campaign_recipients` rows immediately.
   - `POST /api/admin/campaigns/{channel}/{id}/launch`: preserves synchronous admin dispatch using the exact same job materialization, consent verification, idempotency keys, and status reconciliation helpers.
2. **Standalone Worker Process (`python -m app.worker`)**:
   - Runs outside FastAPI (`uvicorn`).
   - Polls PostgreSQL on a configurable interval (`CAMPAIGN_WORKER_POLL_INTERVAL_SECONDS`, default `30s`).
   - Recovers stale processing locks (`locked_at < now - CAMPAIGN_WORKER_STALE_LOCK_SECONDS`).
   - Claims due `SCHEDULED` campaigns and `QUEUED` / `RETRYING` `campaign_recipients` atomically via `SELECT ... FOR UPDATE SKIP LOCKED` in short transactions, committing the `processing` claim **before** executing external provider HTTP calls.
   - Re-checks customer account status and channel consent (`email_marketing_consent` / `whatsapp_marketing_consent`) right before external HTTP delivery; unsubscribed recipients transition to `skipped`.
3. **Webhooks (`/api/webhooks/email`, `/api/webhooks/whatsapp`)**:
   - Signature-verified callbacks update `accepted` / `sent` recipients asynchronously to `delivered`, `read`, `bounced`, `suppressed`, or `failed`, deduplicated through `marketing_webhook_events(provider, event_id)`.

---

## 2. Running & Stopping the Worker Process

From `backend/` with the virtual environment activated:

```bash
# Start continuous worker daemon (default 30s polling from env)
python -m app.worker

# Custom interval and batch size
python -m app.worker --poll-interval 15 --batch-size 100

# Single-pass execution (useful for cron/smoke checks)
python -m app.worker --once
```

### Graceful Shutdown
Send `SIGINT` (`Ctrl+C`) or `SIGTERM` to the worker process. The worker wakes immediately from sleep, completes any active recipient database update, marks its `worker_heartbeats` record as `stopped`, closes DB connections cleanly, and exits with code `0`.

---

## 3. Environment Variables

All credentials are configured strictly via environment variables (see `.env.example` for placeholders):

| Variable | Purpose | Default |
|---|---|---|
| `RESEND_API_KEY` | Resend API secret key | `None` (dev sink used outside prod) |
| `RESEND_FROM_EMAIL` | Sender email address | `DIGI-VERSE <noreply@digiverse.internal>` |
| `RESEND_FROM_NAME` | Sender display name | `DIGI-VERSE` |
| `RESEND_WEBHOOK_SECRET` | Resend/Svix signing secret (`whsec_...`) | `None` |
| `WHATSAPP_ACCESS_TOKEN` | Meta Cloud API permanent/system token | `None` (dev sink used outside prod) |
| `WHATSAPP_PHONE_NUMBER_ID` | Meta WhatsApp Business Phone Number ID | `None` |
| `WHATSAPP_GRAPH_API_VERSION` | Meta Graph API version | `v20.0` |
| `WHATSAPP_APP_SECRET` | Meta App Secret (`X-Hub-Signature-256`) | `None` |
| `WHATSAPP_WEBHOOK_VERIFY_TOKEN` | Meta GET challenge verification token | `None` |
| `CAMPAIGN_WORKER_POLL_INTERVAL_SECONDS` | Worker polling interval (seconds) | `30` |
| `CAMPAIGN_WORKER_BATCH_SIZE` | Recipient jobs claimed per batch | `50` |
| `CAMPAIGN_WORKER_STALE_LOCK_SECONDS` | Orphan lock recovery threshold | `300` |
| `CAMPAIGN_MAX_RETRY_ATTEMPTS` | Maximum attempts per recipient job | `5` |
| `CAMPAIGN_RETRY_BASE_SECONDS` | Initial exponential backoff base | `30` |
| `CAMPAIGN_RETRY_MAX_BACKOFF_SECONDS` | Maximum retry backoff cap | `1800` |
| `CAMPAIGN_PROVIDER_TIMEOUT_SECONDS` | Outbound HTTP request timeout | `10.0` |
| `WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS` | Replay window for Resend `svix-timestamp` | `300` |
| `MAX_WEBHOOK_PAYLOAD_BYTES` | Maximum inbound webhook size (bytes) | `1048576` |

---

## 4. Email (Resend) & WhatsApp Cloud Setup

### Resend
1. Verify your sending domain in Resend and set `RESEND_FROM_EMAIL` & `RESEND_FROM_NAME`.
2. Set `RESEND_API_KEY` in `backend/.env`.
3. Register webhook endpoint:
   - **URL**: `https://<api-domain>/api/webhooks/email`
   - **Events**: `email.sent`, `email.delivered`, `email.bounced`, `email.complained`, `email.failed`, `email.delivery_delayed`
4. Copy the Svix signing secret (`whsec_...`) into `RESEND_WEBHOOK_SECRET`.

### Meta WhatsApp Cloud API
1. Configure `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_GRAPH_API_VERSION`, `WHATSAPP_APP_SECRET`, and `WHATSAPP_WEBHOOK_VERIFY_TOKEN`.
2. Register webhook callback URL in the Meta Developer App:
   - **Callback URL**: `https://<api-domain>/api/webhooks/whatsapp`
   - **Verify Token**: matches `WHATSAPP_WEBHOOK_VERIFY_TOKEN`
   - **Subscribed fields**: `messages` (delivery/read/failed status callbacks).
3. Ensure WhatsApp campaign templates (`approved_template_name`) are pre-approved in Meta Business Manager before queueing.

---

## 5. Retry, Idempotency & Failure Behavior

- **Retryable errors**: Connection failures, network errors, HTTP `429` (respecting `Retry-After` capped by `CAMPAIGN_RETRY_MAX_BACKOFF_SECONDS`), HTTP `408`/`409`/`425`/`5xx`, and Resend timeouts. Backoff formula: `min(cap, base * 2^(attempt - 1))`.
- **Permanent errors**: Invalid email / E.164 phone format, unconfigured credentials, HTTP `400`/`401`/`403`/`404`/`422`. Immediately marked `failed` without consuming retries.
- **Provider Idempotency Keys**:
  - **Resend**: Every recipient job persists a stable `idempotency_key` sent via Resend's `Idempotency-Key` HTTP header across automatic retries so timed-out requests do not double-send.
  - **Meta WhatsApp Cloud API**: Meta Graph `POST /{phone_id}/messages` does not support client-supplied `Idempotency-Key` headers. Pre-submission connection failures (`ConnectTimeout`/`ConnectError`) retry safely; post-submission `ReadTimeout` errors are recorded as `timeout_after_submission` (`retryable=False`) to prevent duplicate WhatsApp messages, while still allowing matching `wamid` webhook reconciliation.
- **Out-of-Order & Terminal Guards**: Webhooks ignore duplicate `(provider, event_id)` events cleanly and never downgrade `delivered`/`read` or revert terminal `bounced`/`suppressed`/`failed`/`skipped` rows.

---

## 6. Database Migrations

Apply or verify migrations against the target database:

```bash
alembic upgrade head
```

Phase 8.2 revision: `b8c9d0e1f234` (`phase8_2_campaign_worker_and_webhooks`), revising `f4b9c2d8a102`.

---

## 7. Automated Local Testing & Staging Verification Checklist

### Local Automated Tests (`digiverse_test` only)
```bash
pytest -v tests/test_campaign_worker_and_webhooks.py
pytest -q
```

### Staging Verification Checklist
1. Confirm `ENVIRONMENT` / secrets (`RESEND_*`, `WHATSAPP_*`) are populated cleanly in staging environment (never committed).
2. Run `alembic upgrade head` on staging DB.
3. Start API (`uvicorn app.main:app`) and standalone worker (`python -m app.worker`).
4. Create a test campaign targeting controlled staging opt-in accounts and click **Queue Worker** in Admin Marketing.
5. Confirm worker heartbeat updates in `GET /api/admin/marketing/worker-status` and recipients transition `queued -> accepted -> delivered` after real provider webhooks hit `/api/webhooks/email` or `/api/webhooks/whatsapp`.
6. Trigger an unsubscribe between queueing and worker pickup to confirm live `skipped` enforcement.
7. Trigger `GET /api/webhooks/whatsapp` with wrong `hub.verify_token` (`403`) and wrong signatures on `POST` webhooks (`401`).

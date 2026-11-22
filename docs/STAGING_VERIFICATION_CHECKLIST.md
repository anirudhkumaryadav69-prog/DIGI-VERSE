# DIGI-VERSE Staging Verification Checklist

Use this checklist before promoting any release candidate from staging to production.

---

## 1. Infrastructure, Configuration & Security Baseline

- [ ] Staging database `digiverse_staging` is isolated from production `digiverse` and test `digiverse_test`.
- [ ] `alembic current` reports `b8c9d0e1f234 (head)`.
- [ ] `python backend/scripts/verify_staging_readiness.py --check-storage` exits `0`.
- [ ] `GET https://staging.your-domain.example/api/health` returns `200 OK` (`database.status == "connected"`).
- [ ] `GET https://staging.your-domain.example/api/ready` returns `200 OK` (`status == "ready"`).
- [ ] `GET https://staging.your-domain.example/api/docs` and `/api/redoc` return `404` (`DEBUG=False`).
- [ ] HTTPS enforced on frontend and API; `COOKIE_SECURE=True`, `SameSite=Strict` admin cookies set cleanly on same-origin `/api` proxy.
- [ ] Frontend build `dist/assets/*.js` contains zero `localhost:8000` URLs and zero secrets.
- [ ] Private R2/S3 bucket rejects anonymous unauthenticated HTTP GETs (Public Access Blocked).
- [ ] Background worker heartbeat appears fresh in `worker_heartbeats` table (`python -m app.worker`).

---

## 2. Functional End-to-End Staging Workflows (A–F)

### Workflow A — Admin Asset Lifecycle (Private S3/R2)
- [ ] Admin logs in cleanly with HTTPS CSRF cookie (`X-CSRF-Token`).
- [ ] Admin creates or selects a digital product and uploads an authentic binary file (PDF/ZIP) via `/api/admin/products/{id}/asset`.
- [ ] Direct unauthenticated object storage URL is inaccessible; DB stores private `asset_storage_key`, `asset_sha256`, and `asset_size_bytes`.

### Workflow B — Customer Checkout & Razorpay Test Purchase
- [ ] Customer registers / logs in and adds the digital product to cart.
- [ ] Checkout initializes a Razorpay Test Mode order (`rzp_test_...`).
- [ ] Razorpay Test checkout completes and verifies signature (or `POST /api/payments/webhook` confirms capture idempotently).
- [ ] Order status transitions to `paid` / `completed` and invoice is accessible.

### Workflow C — Authenticated Signed Binary Download & Limits
- [ ] Customer requests a short-lived signed download URL (`POST /api/orders/{order_id}/items/{item_id}/download-link`).
- [ ] Customer downloads the actual uploaded binary via `GET /api/orders/downloads/{token}` and SHA-256 matches uploaded bytes.
- [ ] Reusing a single-use token or exceeding `MAX_DOWNLOADS_PER_ORDER_ITEM` returns `403`/`410`/`429` as designed.
- [ ] Unauthenticated user or different customer attempting download receives `401`/`403`.

### Workflow D — Background Marketing Campaigns & Webhooks
- [ ] Admin schedules/launches an Email campaign (`Resend`) and WhatsApp template campaign (`Meta Cloud API`).
- [ ] Worker claims `queued` recipients via `FOR UPDATE SKIP LOCKED`, dispatches via provider, and leaves provider-accepted WhatsApp messages non-terminal until webhook confirmation.
- [ ] Signed webhooks (`POST /api/webhooks/email` & `POST /api/webhooks/whatsapp`) update delivery/read/bounced stats idempotently without double-counting duplicates.
- [ ] Opt-out / complaint / bounce updates prevent future recipient targeting.

### Workflow E — Transient Failure & Stale Lock Recovery
- [ ] Simulated transient timeout (`5xx` / timeout) retries with exponential backoff up to `CAMPAIGN_MAX_RETRY_ATTEMPTS`.
- [ ] Ambiguous WhatsApp timeout transitions to recovery-required (`worker_heartbeats` + recipient error state) instead of blindly double-sending.
- [ ] Interrupted worker lock older than `CAMPAIGN_WORKER_STALE_LOCK_SECONDS` is reclaimed safely.

### Workflow F — Backup, Restore & Observability
- [ ] `pg_dump -Fc` backup succeeds and restores cleanly into disposable `digiverse_restore_verify` DB.
- [ ] Restored DB passes `alembic_version == b8c9d0e1f234` and table count check.
- [ ] Backend structured logs, worker error logs, and `4xx`/`5xx` telemetry show no secret leakage (`JWT`, `PGPASSWORD`, API tokens).

# DIGI-VERSE Staging External Providers & Webhook Configuration

> [!IMPORTANT]
> **Live Provider Testing Boundary**
> All four external integrations below require external staging accounts and credentials supplied by you. Until staging credentials are provisioned, only local/mocked verification (including `MockTransport` SigV4 testing and signed webhook fixture simulation) is executed locally.

---

## 1. Private Object Storage (Cloudflare R2 or AWS S3)

DIGI-VERSE uses pure-Python AWS Signature Version 4 over HTTPS (`S3PrivateAssetStorageProvider` in [asset_storage_service.py](file:///d:/PROJECTS/DIGI%20VERSE/backend/app/services/asset_storage_service.py)) with no `boto3` dependency required.

### Setup Steps
1. Create a **private** bucket dedicated to staging: `digiverse-staging-private-assets`.
2. **Block all public access** (enable AWS Block Public Access / disable R2 public dev URL and custom bucket domains). Assets are streamed strictly through authenticated FastAPI downloads (`GET /api/orders/downloads/{token}`) rather than exposed bucket URLs.
3. Create a least-privilege API token / IAM user scoped exclusively to `digiverse-staging-private-assets` (`products/*` object `PutObject`, `GetObject`, `HeadObject`, `DeleteObject`).
4. Configure staging environment variables:
   - `ASSET_STORAGE_BACKEND=s3`
   - `ASSET_STORAGE_BUCKET=digiverse-staging-private-assets`
   - `ASSET_STORAGE_REGION=auto` (for R2) or bucket region (`ap-south-1` for AWS S3)
   - `ASSET_STORAGE_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com` (omit/blank for standard AWS S3)
   - `ASSET_STORAGE_USE_PATH_STYLE=True` (for R2/MinIO; `False` for AWS S3)
5. Run the storage probe check:
   ```bash
   python backend/scripts/verify_staging_readiness.py --check-storage
   ```

---

## 2. Razorpay Test Mode

DIGI-VERSE enforces test-mode keys in staging via `validate_staging_readiness()` (`RAZORPAY_KEY_ID` must begin with `rzp_test_`; `rzp_live_` and `PAYMENT_PROVIDER=mock` are rejected).

### Setup Steps
1. Switch your Razorpay Dashboard toggle to **Test Mode**.
2. Generate API keys and populate:
   - `PAYMENT_PROVIDER=razorpay`
   - `RAZORPAY_KEY_ID=rzp_test_...`
   - `RAZORPAY_KEY_SECRET=...`
3. Register a Staging Webhook in Razorpay Dashboard (Test Mode -> Settings -> Webhooks):
   - **Webhook URL**: `https://staging.your-domain.example/api/payments/webhook`
   - **Secret**: store identical value in `RAZORPAY_WEBHOOK_SECRET`
   - **Events**: `payment.captured`, `payment.failed`, `order.paid`
4. Verify in staging that Razorpay checks `X-Razorpay-Signature` HMAC validation, rejects forged/duplicate webhooks safely (`payment_webhook_events`), and completes customer orders end-to-end.

---

## 3. Resend Staging Email Provider

### Setup Steps
1. Verify a staging sender domain/subdomain (e.g., `staging.your-domain.example`) in Resend (DNS `SPF`, `DKIM`, and `DMARC` TXT/CNAME records).
2. Issue an API key scoped to sending permissions and configure:
   - `RESEND_API_KEY=re_...`
   - `RESEND_FROM_EMAIL=noreply@staging.your-domain.example`
   - `RESEND_FROM_NAME=DIGI-VERSE Staging`
3. Register a Resend Webhook:
   - **Endpoint URL**: `https://staging.your-domain.example/api/webhooks/email`
   - **Events**: `email.sent`, `email.delivered`, `email.bounced`, `email.complained`
   - **Signing Secret**: copy Svix signing secret (`whsec_...`) into `RESEND_WEBHOOK_SECRET`.
4. Confirm transactional & marketing emails render cleanly and bounced/complained addresses record suppression updates via `/api/webhooks/email`.

---

## 4. Meta WhatsApp Cloud API (Staging / Sandbox Test Number)

### Setup Steps
1. In Meta for Developers -> WhatsApp App -> API Setup:
   - Note the staging **Phone Number ID** -> `WHATSAPP_PHONE_NUMBER_ID`.
   - Generate a scoped System User token (test/staging WABA only) -> `WHATSAPP_ACCESS_TOKEN`.
   - Copy App Secret -> `WHATSAPP_APP_SECRET` (required for `X-Hub-Signature-256` HMAC verification).
   - Generate a random string -> `WHATSAPP_WEBHOOK_VERIFY_TOKEN`.
2. Add whitelisted recipient test phone numbers to the Meta Sandbox/Test WABA.
3. Configure approved template messages matching your `message_templates` entries in DIGI-VERSE Admin.
4. Register Meta Webhook Callback URL:
   - **Callback URL**: `https://staging.your-domain.example/api/webhooks/whatsapp`
   - **Verify Token**: matches `WHATSAPP_WEBHOOK_VERIFY_TOKEN` (`GET /api/webhooks/whatsapp` handles `hub.challenge` verification)
   - **Subscribed Fields**: `messages` (covers `sent`, `delivered`, `read`, `failed` status updates via `POST /api/webhooks/whatsapp`).

---

## 5. HTTPS Webhook Endpoint Summary

| Provider | Method & Path | Signature / Verification Header | Replay & Security Controls |
| :--- | :--- | :--- | :--- |
| Razorpay Test Mode | `POST /api/payments/webhook` | `X-Razorpay-Signature` (HMAC-SHA256) | `payment_webhook_events` idempotency, order total verification |
| Resend (Svix) | `POST /api/webhooks/email` | `svix-id`, `svix-timestamp`, `svix-signature` | `WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS` (300s), 1 MB body cap, `marketing_webhook_events` dedup |
| Meta WhatsApp | `GET /api/webhooks/whatsapp` | `hub.mode=subscribe` + `hub.verify_token` | Constant-time token comparison |
| Meta WhatsApp | `POST /api/webhooks/whatsapp` | `X-Hub-Signature-256` (HMAC-SHA256) | Signature enforcement, monotonic status transitions, `marketing_webhook_events` dedup |

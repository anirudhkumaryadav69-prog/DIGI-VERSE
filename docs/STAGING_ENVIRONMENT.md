# DIGI-VERSE Staging Environment & Secrets Reference

> [!CAUTION]
> **Secret Hygiene Rule**
> Never commit real passwords, JWT keys, R2/S3 access keys, Razorpay secrets, Resend keys, or Meta WhatsApp tokens into `.env`, `.env.staging.example`, `render.yaml`, or Git history. Store real secrets only in your deployment platform's encrypted secret manager.

Templates included in repository:
- Backend template: [backend/.env.staging.example](file:///d:/PROJECTS/DIGI%20VERSE/backend/.env.staging.example)
- Frontend template: [frontend/.env.staging.example](file:///d:/PROJECTS/DIGI%20VERSE/frontend/.env.staging.example)

---

## 1. Backend Environment Variables

### Core & Database
| Variable | Required in Staging | Recommended Staging Value / Rule | Notes |
| :--- | :--- | :--- | :--- |
| `ENVIRONMENT` | Yes | `staging` | Activates `validate_staging_readiness()` and hides OpenAPI docs when `DEBUG=False`. |
| `DEBUG` | Yes | `False` | Disables `/api/docs`, `/api/redoc`, `/api/openapi.json`, and detailed traceback responses. |
| `API_V1_PREFIX` | Yes | `/api` | Must match frontend `VITE_API_BASE_URL` or proxy prefix. |
| `DATABASE_URL` | Yes | `postgresql+psycopg://<user>:<pass>@<host>:5432/digiverse_staging?sslmode=require` | Must be a dedicated staging PostgreSQL 17 database. Never point staging to production `digiverse` or local `digiverse_test`. |
| `DB_CONNECT_TIMEOUT` | No | `5` | Connection timeout in seconds. |
| `DB_POOL_SIZE` | No | `10` | SQLAlchemy persistent pool size per worker. |
| `DB_MAX_OVERFLOW` | No | `10` | SQLAlchemy overflow connections per worker. |

### Authentication, Cookies & HTTP Origin Security
| Variable | Required in Staging | Recommended Staging Value / Rule | Notes |
| :--- | :--- | :--- | :--- |
| `JWT_SECRET_KEY` | Yes | 64-hex random string (`python -c "import secrets; print(secrets.token_hex(32))"`) | Signs customer tokens. |
| `ADMIN_JWT_SECRET_KEY` | Yes | Distinct 64-hex random string | **Must differ** from `JWT_SECRET_KEY`. |
| `COOKIE_SECURE` | Yes | `True` | Enforced by `validate_staging_readiness()`. |
| `COOKIE_DOMAIN` | Conditional | Empty when using same-origin `/api` proxy | Set `.staging.your-domain.example` only for custom subdomains sharing a parent domain. |
| `TRUST_PROXY_HEADERS` | Yes | `True` | Allows rate limiter and audit logs to inspect `X-Forwarded-For` behind reverse proxy. |
| `CORS_ORIGINS` | Yes | `["https://staging.your-domain.example"]` | JSON array; `validate_staging_readiness()` rejects `http://`, `localhost`, and `127.0.0.1`. |
| `ALLOWED_HOSTS` | Yes | `["staging.your-domain.example","api-staging.your-domain.example"]` | JSON array for `TrustedHostMiddleware`. |
| `RATE_LIMIT_USE_DB` | Yes | `True` | Shares rate-limit counters across multiple Uvicorn workers in PostgreSQL. |

### Private Asset Storage (S3 / Cloudflare R2)
| Variable | Required in Staging | Recommended Staging Value / Rule | Notes |
| :--- | :--- | :--- | :--- |
| `ASSET_STORAGE_BACKEND` | Yes | `s3` | Enforced by `validate_staging_readiness()`. |
| `ASSET_STORAGE_BUCKET` | Yes | `digiverse-staging-private-assets` | Private bucket only; zero public object ACLs. |
| `ASSET_STORAGE_REGION` | Yes | `auto` (R2) or AWS region (`ap-south-1`) | Signed in AWS SigV4 requests. |
| `ASSET_STORAGE_ENDPOINT_URL` | Conditional | `https://<account_id>.r2.cloudflarestorage.com` | Required for Cloudflare R2, MinIO, or S3-compatible stores. |
| `ASSET_STORAGE_ACCESS_KEY` | Yes | Bucket-scoped IAM / R2 API token key ID | Write/Get/Head/Delete on `products/*` only. |
| `ASSET_STORAGE_SECRET_KEY` | Yes | Bucket-scoped secret access key | Keep encrypted in platform secret store. |
| `ASSET_STORAGE_USE_PATH_STYLE` | Yes | `True` (R2/MinIO) or `False` (AWS virtual-host) | Controls SigV4 URL path style. |
| `MAX_ASSET_UPLOAD_BYTES` | No | `104857600` (100 MB) | Enforced both in headers and streamed chunk accounting. |
| `ASSET_DOWNLOAD_CHUNK_BYTES` | No | `65536` (64 KB) | Streaming chunk size for authenticated download endpoint. |
| `MAX_DOWNLOADS_PER_ORDER_ITEM` | No | `5` | Purchase download cap. |
| `SIGNED_DOWNLOAD_TOKEN_EXPIRE_SECONDS` | No | `300` (5 minutes) | Short-lived download token lifetime. |

### Payment Gateway (Razorpay Test Mode)
| Variable | Required in Staging | Recommended Staging Value / Rule | Notes |
| :--- | :--- | :--- | :--- |
| `STORE_CURRENCY` | Yes | `INR` | Store base currency. |
| `PAYMENT_PROVIDER` | Yes | `razorpay` | `mock` is blocked in staging by `validate_staging_readiness()`. |
| `RAZORPAY_KEY_ID` | Yes | `rzp_test_...` | Staging enforces `rzp_test_` prefix (`rzp_live_` is rejected). |
| `RAZORPAY_KEY_SECRET` | Yes | Razorpay Test Key Secret | Used for checkout order creation & signature verification. |
| `RAZORPAY_WEBHOOK_SECRET` | Yes | Razorpay Staging Webhook Secret | Verifies `X-Razorpay-Signature`. |

### Marketing Delivery, Background Worker & Webhooks
| Variable | Required in Staging | Recommended Staging Value / Rule | Notes |
| :--- | :--- | :--- | :--- |
| `RESEND_API_KEY` | Yes (for live email) | `re_...` | Resend staging API key. |
| `RESEND_FROM_EMAIL` | Yes | Verified staging sender (`noreply@staging.your-domain.example`) | Domain must pass SPF/DKIM in Resend. |
| `RESEND_FROM_NAME` | No | `DIGI-VERSE Staging` | Display sender name. |
| `RESEND_WEBHOOK_SECRET` | Yes | `whsec_...` | Verifies Svix/Resend webhook signatures. |
| `WHATSAPP_ACCESS_TOKEN` | Yes (for live WA) | Meta system user test token | Scoped to staging WhatsApp Business test account. |
| `WHATSAPP_PHONE_NUMBER_ID` | Yes (for live WA) | Meta test phone number ID | Target sender phone ID. |
| `WHATSAPP_GRAPH_API_VERSION` | No | `v20.0` | Meta Graph API version. |
| `WHATSAPP_APP_SECRET` | Yes | Meta App Secret | Verifies `X-Hub-Signature-256` HMAC signatures. |
| `WHATSAPP_WEBHOOK_VERIFY_TOKEN` | Yes | Random verify token string | Validates Meta webhook `GET` challenge. |
| `CAMPAIGN_WORKER_POLL_INTERVAL_SECONDS` | No | `30` | Worker DB poll cadence. |
| `CAMPAIGN_WORKER_BATCH_SIZE` | No | `50` | Max recipients claimed per poll cycle. |
| `CAMPAIGN_WORKER_STALE_LOCK_SECONDS` | No | `300` | Reclaim threshold for crashed worker locks. |
| `CAMPAIGN_MAX_RETRY_ATTEMPTS` | No | `5` | Max retries before terminal failure. |
| `CAMPAIGN_RETRY_BASE_SECONDS` | No | `30` | Initial exponential backoff delay. |
| `CAMPAIGN_RETRY_MAX_BACKOFF_SECONDS` | No | `1800` | Maximum exponential backoff delay. |
| `CAMPAIGN_PROVIDER_TIMEOUT_SECONDS` | No | `10.0` | HTTP timeout for Resend/Meta API calls. |
| `WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS` | No | `300` | Anti-replay window for signed webhooks. |
| `MAX_WEBHOOK_PAYLOAD_BYTES` | No | `1048576` (1 MB) | Protects webhook endpoints from oversized payloads. |

---

## 2. Frontend Build Environment Variables

| Variable | Required in Staging | Staging Value | Notes |
| :--- | :--- | :--- | :--- |
| `VITE_API_BASE_URL` | Yes | `/api` (same-origin proxy) or `https://api-staging.your-domain.example/api` | Baked into Vite static bundle during `npm run build`. Must never contain `localhost`, `127.0.0.1`, or backend secrets. |

---

## 3. Staging Readiness Validation

Run the pre-flight check before exposing staging traffic:

```bash
cd backend
python scripts/verify_staging_readiness.py --check-storage
```

The script calls `settings.validate_staging_readiness()`, checks PostgreSQL connectivity (`SELECT 1`), confirms `alembic_version` matches the migration head, and runs a disposable write/head/read/delete probe against private storage without printing secrets.

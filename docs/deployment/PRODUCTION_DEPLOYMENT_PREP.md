# DIGI-VERSE — Production Deployment Guide (Render + Managed PG 17 + Cloudflare R2 + Vercel)

## 1. Verified Render Web Service Settings

- **Root Directory**: `backend`
- **Runtime**: Python `3.12` (pinned via `backend/.python-version`)
- **Build Command**: `pip install --no-cache-dir -r requirements.txt`
- **Pre-Deploy Command**: `alembic upgrade head`
- **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1 --proxy-headers --forwarded-allow-ips=*`
- **Health Check Endpoint**: `/api/health` (executes `SELECT 1`; use `/api/ready` for smoke-test verification of capability states)
- **PostgreSQL**: Render Managed PostgreSQL `17` (`DB_SSLMODE=require` secures internal `dpg-*-a` URLs injected by Render's `fromDatabase` connection string without mutating query parameters)

### Worker Memory & Lifecycle Evaluation (`--workers 1` on Starter)

- **Lifecycle**: FastAPI `lifespan()` validates configuration cleanly, and auth sessions plus rate-limit buckets (`RATE_LIMIT_USE_DB=True`) persist in PostgreSQL rather than in-process memory.
- **Initial Starter Configuration**: `--workers 1` is the initial Render Starter (512 MB RAM) configuration because uploaded public images (up to 5 MB) are buffered in heap RAM before writing to R2 and container RAM usage has not yet been benchmarked under live traffic.
- **Scaling Workers**: Increasing `--workers` above `1` (or adding concurrent upload load) requires actual production RSS memory and concurrency benchmarking, and may require upgrading beyond the 512 MB Starter plan.

## 2. Final Vercel Proxy Configuration (`frontend/vercel.json`)

**Do not modify `frontend/vercel.json` until the Render Web Service hostname is live.**
Once `<RENDER_API_HOST>` (for example `digiverse-api.onrender.com`) is assigned by Render, replace `frontend/vercel.json` with:

```json
{
  "headers": [
    {
      "source": "/api/(.*)",
      "headers": [
        { "key": "Cache-Control", "value": "no-store, no-cache, must-revalidate" }
      ]
    },
    {
      "source": "/api/uploads/images/(.*)",
      "headers": [
        { "key": "Cache-Control", "value": "public, max-age=86400" }
      ]
    }
  ],
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://<RENDER_API_HOST>/api/:path*"
    },
    {
      "source": "/((?!api(?:/|$)).*)",
      "destination": "/index.html"
    }
  ]
}
```

### Vercel + Cookie Security Notes

- Leave `VITE_API_BASE_URL` unset (or `/api`) on Vercel so browser requests remain strictly same-origin.
- Leave `COOKIE_DOMAIN` **unset** on Render so browsers enforce host-only cookies scoped strictly to the Vercel origin.
- Set `CORS_ORIGINS` to `["https://<YOUR_VERCEL_DOMAIN>"]` and `ALLOWED_HOSTS` to `["<RENDER_API_HOST>"]` (plus any Vercel-forwarded host if applicable).
- `HttpOnly`, `Secure=True`, customer/CSRF `SameSite=Lax`, admin `SameSite=Strict`, and double-submit `X-CSRF-Token` validation remain fully active without weakening.
- *Proxy payload limit note*: Vercel serverless rewrites typically enforce a ~4.5 MB request body ceiling. Standard API calls and <5 MB images work through Vercel rewrites; for >5 MB private digital asset uploads (up to 100 MB), use a custom domain (`api.<yourdomain>`) or direct presigned R2 uploads in a future phase.

## 3. Cloudflare R2 Bucket Separation & Existing Image Migration Plan

- **Credential Isolation (Mandatory)**: Provision **two separate, bucket-restricted Cloudflare R2 API tokens**:
  - `ASSET_STORAGE_ACCESS_KEY` / `ASSET_STORAGE_SECRET_KEY`: scoped strictly to `ASSET_STORAGE_BUCKET` only (no access to public images).
  - `IMAGE_STORAGE_ACCESS_KEY` / `IMAGE_STORAGE_SECRET_KEY`: scoped strictly to `IMAGE_STORAGE_BUCKET` only (no access to private digital assets).
  - Public image storage never inherits or falls back to private asset credentials.
- **Private Digital Assets (`ASSET_STORAGE_BACKEND=s3`)**:
  - Dedicated private bucket: `ASSET_STORAGE_BUCKET` (block all public access), explicit `ASSET_STORAGE_ENDPOINT_URL` (`https://<account>.r2.cloudflarestorage.com`) when `ASSET_STORAGE_REGION=auto`.
  - Delivered exclusively via authenticated, single-use, 5-minute signed JWT grants (`/api/downloads/{download_id}/file?token=...`).
- **Public Marketplace Images (`IMAGE_STORAGE_BACKEND=s3`)**:
  - Dedicated public-assets bucket: `IMAGE_STORAGE_BUCKET` (must differ from `ASSET_STORAGE_BUCKET`), explicit `IMAGE_STORAGE_ENDPOINT_URL`, `IMAGE_STORAGE_ACCESS_KEY`, and `IMAGE_STORAGE_SECRET_KEY`.
  - Uploaded via `POST /api/admin/.../images` and `POST /api/seller/.../branding`, persisted under `public-images/<uuid32>.<ext>`, and streamed at `/api/uploads/images/{filename}` — preserving 100% of existing database URLs and frontend behavior with zero schema changes.
  - Both `ASSET_STORAGE_BACKEND` and `IMAGE_STORAGE_BACKEND` reject `local` in `production`.

### Migrating Existing Local Public Images (Future Cutover Step)

1. Provision the two R2 buckets and API tokens (`ASSET_STORAGE_*` and `IMAGE_STORAGE_*`).
2. Copy existing files from local `backend/uploads/images/<uuid32>.<ext>` into the R2 `IMAGE_STORAGE_BUCKET` under key `public-images/<uuid32>.<ext>` (preserving filenames verbatim and without deleting local copies until verified).
3. Verify `HEAD` parity against DB URLs (`/api/uploads/images/<filename>`), then switch Render `IMAGE_STORAGE_BACKEND=s3`.

## 4. Provider States & Feature Availability When Unconfigured

| Integration | Safe Pre-Launch Production Setting | Behavior When Disabled |
|---|---|---|
| Razorpay | `PAYMENTS_ENABLED=False`, `PAYMENT_PROVIDER=disabled` | Core catalog/cart/auth boot normally; `/api/checkout`, `/api/payments/verify`, `/api/payments/webhook`, `/api/orders/{id}/retry-payment` return `503`. Test keys (`rzp_test_*`) are never treated as live. |
| Cloudflare R2 | `ASSET_STORAGE_BACKEND=disabled`, `IMAGE_STORAGE_BACKEND=disabled` | Never falls back to local disk; upload and retrieval endpoints fail closed (`503`). |
| Resend Email | `EMAIL_ENABLED=False` | Core marketplace boots; `/api/auth/forgot-password` returns `503` without enumeration or fake emails; transactional checkout emails log safely without blocking; email campaigns fail closed (`email_disabled`). |
| WhatsApp OTP | `OTP_DELIVERY_PROVIDER=disabled`, `WHATSAPP_OTP_ENABLED=False` | Registration succeeds cleanly (`otp_delivery_status="disabled"`, `is_phone_verified=False`); `/api/auth/otp/send` and phone-change OTP return `503`; `/api/auth/verified-access` remains strictly `403`. |

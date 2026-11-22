# DIGI-VERSE Staging Database Migration & Rollback Runbook

> [!CAUTION]
> **Database Isolation Mandate**
> - **Production**: `digiverse` — never run test suites, staging scripts, or destructive checks against this database.
> - **Automated Test**: `digiverse_test` — used exclusively by automated pytest integration tests.
> - **Staging**: Provision a dedicated empty PostgreSQL 17 database (`digiverse_staging`) for staging deployments.

---

## 1. Alembic Migration Lineage

Verified repository Alembic chain (`alembic history`):

```text
<base>
  └─> 3b9aa73cb927  (initial core schema)
        └─> a67e85f7cce0  (phase 7 security/audit/rate-limit extensions)
              └─> 4257bac0fc28  (phase 7 indexes & constraints)
                    └─> bcf03aa639b3  (phase 7.1 head / current local production DB baseline)
                          └─> e1a7f3c9d201  (phase 8.1 private digital asset columns on products & audit support)
                                └─> f4b9c2d8a102  (phase 8.2 persistent campaigns, recipients, webhook events & suppressions)
                                      └─> b8c9d0e1f234  (head: phase 8.2 audit constraints, idempotency keys & indexes)
```

Expected staging head revision: **`b8c9d0e1f234`**.

---

## 2. Pre-Migration Backup Checklist

Before upgrading any existing staging or production database from `bcf03aa639b3` to `b8c9d0e1f234`:

1. Ensure no long-running write transactions or active campaign workers are holding table locks (`worker` scaled to 0 during major schema upgrades).
2. Create a verified custom-format PostgreSQL backup:
   ```bash
   python backend/scripts/backup_and_verify_restore.py \
     --source-url "$STAGING_DATABASE_URL" \
     --backup-file "./backups/pre_migration_$(date -u +%Y%m%dT%H%M%SZ).dump" \
     --verify-restore-db digiverse_restore_verify
   ```
3. Confirm `alembic current` matches the expected prior baseline (`bcf03aa639b3` for upgrades, or empty on fresh staging DB).

---

## 3. Staging Migration Sequence

Run migrations **against staging only** (`DATABASE_URL` pointing to `digiverse_staging`):

```bash
cd backend
alembic upgrade head
alembic current
```

Expected output after completion:
```text
b8c9d0e1f234 (head)
```

For fresh staging PostgreSQL provisioning, `alembic upgrade head` executes the entire chain `<base> -> b8c9d0e1f234` deterministically in sequence, creating all marketplace, Phase 8.1 digital-asset, and Phase 8.2 campaign/webhook tables, constraints, and indexes.

---

## 4. Schema & Operational Verification Queries

After running `alembic upgrade head`, verify key Phase 8.1 and 8.2 objects exist:

```sql
SELECT version_num FROM alembic_version;

SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

Confirm critical tables exist (30 application tables plus `alembic_version`):
`admins`, `audit_logs`, `auth_sessions`, `phone_otp_challenges`, `password_reset_tokens`, `rate_limit_buckets`, `message_templates`, `email_campaigns`, `whatsapp_campaigns`, `campaign_recipients`, `marketing_webhook_events`, `worker_heartbeats`, `categories`, `products`, `product_images`, `sales`, `banners`, `advertisement_videos`, `customers`, `customer_activities`, `login_history`, `orders`, `order_items`, `payments`, `download_records`, `payment_webhook_events`, `store_settings`, `wishlists`, `carts`, `cart_items`.

Confirm `verify_staging_readiness.py` reports matching head:
```bash
python scripts/verify_staging_readiness.py
```

---

## 5. Rollback Procedures

### Option A: Safe Schema Downgrade (No Data Loss Needed Beyond Rolled-Back Columns)
If deployment fails smoke checks right after upgrading and no new staging data must be preserved in Phase 8.1/8.2 tables:

```bash
cd backend
# Stop web and worker processes first, then downgrade step-by-step or back to baseline:
alembic downgrade bcf03aa639b3
```

> [!WARNING]
> Downgrading from `b8c9d0e1f234` to `bcf03aa639b3` drops Phase 8.1 asset metadata columns and Phase 8.2 campaign/webhook tables. Always prefer database snapshot restore if production/staging records created post-migration must be audited first.

### Option B: Full Point-in-Time / Snapshot Restore (Recommended for Safe Recovery)
Restore the pre-migration `.dump` file into a clean database via `pg_restore` (see [STAGING_BACKUP_RESTORE.md](file:///d:/PROJECTS/DIGI%20VERSE/docs/STAGING_BACKUP_RESTORE.md)) and re-deploy the prior release tag.

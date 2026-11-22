# DIGI-VERSE Staging Backup, Restore & Disaster Recovery Guide

> [!CAUTION]
> **Production Safety Rule**
> Never test restore commands against `digiverse`. Always validate backup files by restoring into a **disposable** database such as `digiverse_restore_verify` and dropping that disposable database immediately afterward.

---

## 1. Automated Verification Utility (`backup_and_verify_restore.py`)

Repository script: [backend/scripts/backup_and_verify_restore.py](file:///d:/PROJECTS/DIGI%20VERSE/backend/scripts/backup_and_verify_restore.py)

Capabilities & built-in guards:
- Uses PostgreSQL `pg_dump -Fc --no-owner --no-privileges` (custom compressed format).
- Refuses disposable targets named `digiverse` or `postgres`, and requires `verify` or `restore` in the disposable database name.
- Passes DB password via `PGPASSWORD` environment variable so secrets are never printed to CLI args or logs.
- Restores backup into the temporary DB via `pg_restore`, queries `alembic_version` and `information_schema.tables` table count, and terminates/drops the temporary database inside a `finally` block.

### Usage Example (Staging)
```bash
# Full disposable-database restore drill (pass --admin-url if app role lacks CREATEDB):
python backend/scripts/backup_and_verify_restore.py \
  --source-url "postgresql+psycopg://app_user:PASSWORD@127.0.0.1:5432/digiverse_staging" \
  --admin-url "postgresql+psycopg://postgres:ADMIN_PASS@127.0.0.1:5432/postgres" \
  --backup-file "./backups/digiverse_staging_manual.dump" \
  --verify-restore-db digiverse_restore_verify

# Least-privilege backup + TOC integrity check without CREATEDB:
python backend/scripts/backup_and_verify_restore.py \
  --source-url "postgresql+psycopg://app_user:PASSWORD@127.0.0.1:5432/digiverse_staging" \
  --backup-file "./backups/digiverse_staging_manual.dump" \
  --list-only
```

---

## 2. Recommended Staging & Production Backup Policy

1. **Automated Managed Snapshots**: Enable daily automated snapshots + WAL archiving / Point-In-Time Recovery (PITR) on managed PostgreSQL (Render Managed Postgres / RDS / Neon).
2. **Pre-Deploy Logical Dumps**: Capture a custom-format `pg_dump -Fc` snapshot immediately before running `alembic upgrade head` on staging or production upgrades.
3. **Periodic Restore Drills**: Run `backup_and_verify_restore.py` weekly or prior to major schema migrations to confirm backups are non-empty, uncorrupted, and restorable.
4. **Private Object Bucket Versioning**: Enable bucket object versioning (and lifecycle rules for old versions) on `digiverse-staging-private-assets` so accidentally deleted product binaries can be recovered.

---

## 3. Manual Disaster Recovery Restore Procedure

If staging database corruption occurs:

1. **Stop writers**: Scale web API (`uvicorn`) and background worker (`python -m app.worker`) to `0` replicas so no in-flight connections hold locks.
2. **Create fresh clean target database**:
   ```sql
   DROP DATABASE IF EXISTS digiverse_staging_recovered;
   CREATE DATABASE digiverse_staging_recovered;
   ```
3. **Restore verified archive**:
   ```bash
   pg_restore -h <host> -p 5432 -U <user> --no-owner --no-privileges -d digiverse_staging_recovered /path/to/backup.dump
   ```
4. **Verify Alembic & row counts**:
   ```bash
   psql -d digiverse_staging_recovered -c "SELECT version_num FROM alembic_version;"
   ```
5. **Switch `DATABASE_URL`** (or rename databases during maintenance window), re-run `python backend/scripts/verify_staging_readiness.py --check-storage`, and restart web + worker processes.

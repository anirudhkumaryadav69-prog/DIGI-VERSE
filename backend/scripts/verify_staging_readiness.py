"""Pre-flight verification script for DIGI-VERSE staging deployments.

Checks (read-only / disposable probe object only):
1. Environment staging readiness (`validate_staging_readiness`).
2. Database connectivity (`SELECT 1`) and Alembic revision head check.
3. Private asset storage round-trip probe (when `--check-storage` is passed).

Never exposes secret values in output.
"""
from __future__ import annotations

import argparse
import io
import os
import sys
import uuid
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.core.database import check_database_connection, engine
from app.services.asset_storage_service import get_asset_storage


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify DIGI-VERSE staging readiness.")
    parser.add_argument(
        "--check-storage",
        action="store_true",
        help="Verify private asset storage backend via write/head/read/delete probe.",
    )
    args = parser.parse_args()

    print(f"Environment: {settings.ENVIRONMENT}")

    issues = settings.validate_staging_readiness()
    if issues:
        print("Configuration issues:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("Configuration check: OK")

    db_ok, db_err = check_database_connection()
    print(f"Database connectivity: {'OK' if db_ok else f'FAILED ({db_err})'}")

    rev_match = False
    if db_ok:
        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
        script_dir = ScriptDirectory.from_config(cfg)
        expected_heads = set(script_dir.get_heads())
        with engine.connect() as conn:
            current_rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        rev_match = current_rev in expected_heads
        print(f"Alembic revision: {current_rev} (expected head(s): {sorted(expected_heads)}, match={rev_match})")

    storage_ok = True
    if args.check_storage:
        try:
            provider = get_asset_storage()
            probe_key = f"products/readiness-probe/{uuid.uuid4().hex}.txt"
            payload = b"digiverse-staging-storage-probe"
            meta = provider.save(io.BytesIO(payload), probe_key, "text/plain", len(payload))
            exists_ok = provider.exists(probe_key)
            handle = provider.open(probe_key)
            read_back = b"".join(handle.iter_chunks())
            provider.delete(probe_key)
            storage_ok = bool(exists_ok and read_back == payload and meta.storage_backend == provider.backend_name)
            print(f"Private storage ({provider.backend_name}): {'OK' if storage_ok else 'FAILED'}")
        except Exception as exc:  # noqa: BLE001
            storage_ok = False
            print(f"Private storage: FAILED ({exc.__class__.__name__})")

    return 0 if (not issues and db_ok and rev_match and storage_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Backup & disposable-database restore verification utility for PostgreSQL 17.

Safety rules:
- Refuses to restore into production (`digiverse`) or overwrite any non-disposable target.
- Never prints or logs PostgreSQL passwords (`DATABASE_URL` credentials are passed via PGPASSWORD).
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

DB_NAME_RE = re.compile(r"^[a-zA-Z0-9_]+$")


def _find_pg_tool(tool_name: str) -> str:
    import shutil

    on_path = shutil.which(tool_name)
    if on_path:
        return on_path
    for candidate in Path(r"C:\Program Files\PostgreSQL").glob(f"*/bin/{tool_name}.exe"):
        return str(candidate)
    raise FileNotFoundError(f"Could not locate PostgreSQL binary '{tool_name}'.")


def _pg_env(url_obj) -> dict[str, str]:
    env = os.environ.copy()
    if url_obj.password:
        env["PGPASSWORD"] = url_obj.password
    return env


def run_backup(source_url: str, backup_path: Path) -> None:
    u = make_url(source_url)
    pg_dump = _find_pg_tool("pg_dump")
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        pg_dump,
        "-h",
        u.host or "localhost",
        "-p",
        str(u.port or 5432),
        "-U",
        u.username or "postgres",
        "-Fc",
        "--no-owner",
        "--no-privileges",
        "-f",
        str(backup_path),
        u.database or "",
    ]
    res = subprocess.run(cmd, env=_pg_env(u), capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {res.stderr.strip()}")
    print(f"Backup created successfully: {backup_path} ({backup_path.stat().st_size} bytes)")


def verify_archive_toc(backup_path: Path) -> list[str]:
    """Validate custom-format dump readability using `pg_restore --list` (works with least-privilege roles)."""
    pg_restore = _find_pg_tool("pg_restore")
    res = subprocess.run([pg_restore, "--list", str(backup_path)], capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"pg_restore --list failed: {res.stderr.strip()}")
    entries = [ln for ln in res.stdout.splitlines() if ln.strip() and not ln.strip().startswith(";")]
    print(f"Archive TOC verified: {len(entries)} restorable entries in {backup_path.name}")
    return entries


def verify_restore(
    source_url: str,
    backup_path: Path,
    verify_db_name: str,
    *,
    admin_url_override: str | None = None,
) -> None:
    if not DB_NAME_RE.match(verify_db_name) or verify_db_name in {"digiverse", "postgres"}:
        raise ValueError(f"Unsafe disposable restore database name: {verify_db_name}")
    if "verify" not in verify_db_name and "restore" not in verify_db_name:
        raise ValueError("Disposable restore DB name must contain 'verify' or 'restore'.")

    u = make_url(admin_url_override or source_url)
    admin_url = u.set(database="postgres")
    target_url = u.set(database=verify_db_name)
    pg_restore = _find_pg_tool("pg_restore")

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{verify_db_name}"'))
            conn.execute(text(f'CREATE DATABASE "{verify_db_name}"'))

        cmd = [
            pg_restore,
            "-h",
            u.host or "localhost",
            "-p",
            str(u.port or 5432),
            "-U",
            u.username or "postgres",
            "--no-owner",
            "--no-privileges",
            "-d",
            verify_db_name,
            str(backup_path),
        ]
        res = subprocess.run(cmd, env=_pg_env(u), capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"pg_restore failed: {res.stderr.strip()}")

        verify_engine = create_engine(target_url)
        try:
            with verify_engine.connect() as conn:
                rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
                tables = conn.execute(
                    text("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")
                ).scalar()
            print(f"Restore verified in '{verify_db_name}': alembic_version={rev}, public_tables={tables}")
        finally:
            verify_engine.dispose()
    finally:
        try:
            with admin_engine.connect() as conn:
                conn.execute(
                    text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :db AND pid <> pg_backend_pid()"
                    ),
                    {"db": verify_db_name},
                )
                conn.execute(text(f'DROP DATABASE IF EXISTS "{verify_db_name}"'))
        finally:
            admin_engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="DIGI-VERSE PostgreSQL backup & disposable restore check")
    parser.add_argument("--source-url", required=True, help="PostgreSQL connection URI to back up")
    parser.add_argument("--backup-file", required=True, help="Output .dump file path")
    parser.add_argument(
        "--admin-url",
        default=None,
        help="Optional DBA PostgreSQL URI with CREATEDB privilege when --source-url uses least privilege",
    )
    parser.add_argument(
        "--verify-restore-db",
        default="digiverse_restore_verify",
        help="Disposable database name to test pg_restore and then drop",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Verify dump archive readability via `pg_restore --list` without requiring CREATEDB",
    )
    args = parser.parse_args()

    backup_path = Path(args.backup_file).resolve()
    run_backup(args.source_url, backup_path)
    verify_archive_toc(backup_path)
    if not args.list_only:
        verify_restore(
            args.source_url,
            backup_path,
            args.verify_restore_db,
            admin_url_override=args.admin_url,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

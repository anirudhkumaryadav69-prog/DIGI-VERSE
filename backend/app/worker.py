"""Standalone persistent background campaign worker process.

Usage:
    python -m app.worker [--once] [--poll-interval 30] [--batch-size 50]
"""
from __future__ import annotations

import argparse
import logging
import os
import signal
import socket
import threading
import uuid

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.logging import log_background_event
from app.services.campaign_worker import record_worker_heartbeat, run_worker_cycle


def build_worker_id() -> str:
    return f"worker-{socket.gethostname()[:30]}-{os.getpid()}-{uuid.uuid4().hex[:6]}"


def run_worker_loop(
    *,
    poll_interval_seconds: int,
    batch_size: int,
    run_once: bool = False,
    stop_event: threading.Event | None = None,
) -> int:
    shutdown_event = stop_event or threading.Event()
    worker_id = build_worker_id()
    interval = max(1, int(poll_interval_seconds))

    log_background_event(
        "worker.started",
        level=logging.INFO,
        worker_id=worker_id,
        poll_interval_seconds=interval,
        batch_size=batch_size,
        run_once=run_once,
    )

    try:
        while not shutdown_event.is_set():
            try:
                stats = run_worker_cycle(
                    SessionLocal,
                    worker_id=worker_id,
                    batch_size=batch_size,
                )
                if any(stats.values()):
                    log_background_event(
                        "worker.cycle_completed",
                        level=logging.INFO,
                        worker_id=worker_id,
                        **stats,
                    )
            except Exception as exc:  # noqa: BLE001
                log_background_event(
                    "worker.cycle_error",
                    level=logging.ERROR,
                    worker_id=worker_id,
                    error_type=exc.__class__.__name__,
                )
            if run_once:
                break
            shutdown_event.wait(timeout=interval)
    finally:
        try:
            with SessionLocal() as db:
                record_worker_heartbeat(db, worker_id=worker_id, status_str="stopped")
                db.commit()
        except Exception:  # noqa: BLE001
            pass
        engine.dispose()
        log_background_event("worker.stopped", level=logging.INFO, worker_id=worker_id)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="DIGI-VERSE Persistent Campaign Delivery Worker")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Execute one polling cycle and exit cleanly.",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=settings.CAMPAIGN_WORKER_POLL_INTERVAL_SECONDS,
        help="Seconds between worker polling cycles (default from CAMPAIGN_WORKER_POLL_INTERVAL_SECONDS).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=settings.CAMPAIGN_WORKER_BATCH_SIZE,
        help="Maximum recipient delivery jobs claimed per polling cycle.",
    )
    args = parser.parse_args()

    stop_event = threading.Event()

    def _handle_signal(signum, _frame):  # pragma: no cover - OS signal hook
        log_background_event("worker.shutdown_signal_received", level=logging.INFO, signal=signum)
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_signal)

    return run_worker_loop(
        poll_interval_seconds=args.poll_interval,
        batch_size=args.batch_size,
        run_once=args.once,
        stop_event=stop_event,
    )


if __name__ == "__main__":
    raise SystemExit(main())

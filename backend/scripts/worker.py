"""Background worker: reservation sweep and notification retries.

Why this exists as a separate process
-------------------------------------
The sweep used to run as an ``asyncio`` task inside every API replica. That has
two problems at production scale:

1. **Duplicated work.** N replicas each scanned and locked the same expired
   orders every minute. (Correctness is now protected by ``FOR UPDATE SKIP
   LOCKED`` in ``order_service.sweep_expired_reservations``, so nothing is
   double-applied — but the contention and the wasted connections were real.)
2. **Coupled scaling.** Web traffic and background work compete for the same
   CPU and the same database pool. A traffic spike could delay stock release,
   and a slow sweep could add latency to checkouts.

Running it here means the API can scale out horizontally while exactly one
worker (or several, safely) handles background duties.

The API still starts its own in-process sweep when ``RUN_INLINE_SWEEP=true`` so
that a single-container deployment — or local development — works with no extra
service. Set it to ``false`` in production once this worker is running.

Run:
    python -m scripts.worker
"""

import os
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.logging import get_logger  # noqa: E402
from app.services import notification_service, order_service  # noqa: E402

log = get_logger("worker")

# Intervals are short enough that an unpaid order's stock returns to the pool
# promptly, but long enough that idle polling does not hammer the database.
SWEEP_INTERVAL_SECONDS = int(os.environ.get("SWEEP_INTERVAL_SECONDS", "60"))
NOTIFICATION_INTERVAL_SECONDS = int(os.environ.get("NOTIFICATION_INTERVAL_SECONDS", "120"))
# Cap retries so a permanently bad address cannot be retried forever.
MAX_NOTIFICATION_ATTEMPTS = int(os.environ.get("MAX_NOTIFICATION_ATTEMPTS", "5"))

_shutdown = False


def _request_shutdown(signum, _frame) -> None:
    """Handle SIGTERM/SIGINT so the platform can stop us between jobs.

    A worker killed mid-transaction would roll back cleanly, but finishing the
    current tick avoids abandoning a half-swept batch and lets the platform's
    graceful-shutdown window succeed.
    """
    global _shutdown
    log.info("received signal %s — finishing current job then exiting", signum)
    _shutdown = True


def sweep_reservations() -> int:
    """Release stock for unpaid orders whose reservation window has elapsed."""
    db = SessionLocal()
    try:
        released = order_service.sweep_expired_reservations(db)
        db.commit()
        if released:
            log.info("released %s expired reservation(s)", released)
        return released
    except Exception:
        db.rollback()
        # Log and continue: one failed tick must not kill the worker. The next
        # tick retries the same rows because nothing was committed.
        log.exception("reservation sweep failed")
        return 0
    finally:
        db.close()


def retry_failed_notifications() -> int:
    """Re-dispatch notifications a provider previously rejected.

    Only transient failures are worth retrying; a 422 (unverified sender, bad
    address) will fail identically every time and is left alone once it has
    exhausted its attempts.
    """
    from sqlalchemy import select

    from app.models.commerce import Notification, NotificationStatus

    db = SessionLocal()
    try:
        pending = db.scalars(
            select(Notification)
            .where(Notification.status == NotificationStatus.failed)
            .where(Notification.retry_count < MAX_NOTIFICATION_ATTEMPTS)
            .order_by(Notification.created_at)
            .limit(50)
        ).all()

        if not pending:
            return 0

        retried = 0
        for row in pending:
            notification_service.retry_notification(db, row)
            retried += 1
        db.commit()
        log.info("retried %s failed notification(s)", retried)
        return retried
    except Exception:
        db.rollback()
        log.exception("notification retry pass failed")
        return 0
    finally:
        db.close()


def _sleep(seconds: int) -> None:
    """Interruptible sleep — polling in 1s slices so SIGTERM is honoured fast."""
    deadline = time.monotonic() + seconds
    while not _shutdown and time.monotonic() < deadline:
        time.sleep(min(1.0, max(0.0, deadline - time.monotonic())))


def main() -> None:
    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)

    log.info(
        "worker starting (env=%s, sweep=%ss, notifications=%ss, db=%s)",
        settings.app_env,
        SWEEP_INTERVAL_SECONDS,
        NOTIFICATION_INTERVAL_SECONDS,
        "postgresql" if not settings.is_sqlite else "sqlite",
    )
    if settings.is_sqlite:
        log.warning(
            "running the worker against SQLite — fine for development, but "
            "production needs PostgreSQL for row locking to be meaningful"
        )

    last_notification_run = 0.0

    while not _shutdown:
        sweep_reservations()

        now = time.monotonic()
        if now - last_notification_run >= NOTIFICATION_INTERVAL_SECONDS:
            retry_failed_notifications()
            last_notification_run = now

        _sleep(SWEEP_INTERVAL_SECONDS)

    log.info("worker stopped cleanly")


if __name__ == "__main__":
    main()

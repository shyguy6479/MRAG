"""Wake the hosted worker after durable admission and during active queue recovery."""

import logging
from typing import Any

from sqlalchemy import update

from atlasrag.core.storage import DocumentRow

logger = logging.getLogger("atlasrag.dispatch")


def dispatch(runtime: Any, *, recover: bool = False) -> bool:
    client = runtime.cache.client
    guard = "mrag:ingestion:recovery"
    if recover and client:
        try:
            if not client.set(guard, "1", nx=True, ex=30):
                return False
        except Exception as exc:
            # A cache outage must not prevent dispatch to the independent durable queue.
            logger.warning(
                "queue_recovery_guard_unavailable",
                extra={
                    "exception_type": type(exc).__name__,
                },
            )
    try:
        from workers.vercel_tasks import poll

        task = poll.delay()
        logger.info("queue_dispatched", extra={"task_id": str(getattr(task, "id", ""))})
        return True
    except Exception as exc:
        # Keep the guard until its TTL expires to avoid flooding a failing queue.
        kind = type(exc).__name__
        logger.error("queue_dispatch_failed", extra={"exception_type": kind})
        try:
            with runtime.ingestion.db.sessions.begin() as session:
                session.execute(
                    update(DocumentRow)
                    .where(DocumentRow.status == "queued")
                    .values(
                        error=(
                            f"Queue dispatch failed ({kind}). "
                            "Stored upload is safe; retrying dispatch."
                        )
                    )
                )
        except Exception as storage_error:
            logger.error(
                "queue_error_record_failed",
                extra={"exception_type": type(storage_error).__name__},
            )
        return False

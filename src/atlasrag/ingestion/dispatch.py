"""Wake the hosted worker after durable admission and during active queue recovery."""

import logging
from typing import Any

logger = logging.getLogger("atlasrag.dispatch")


def dispatch(runtime: Any, *, recover: bool = False) -> None:
    client = runtime.cache.client
    guard = "mrag:ingestion:recovery"
    if recover and client and not client.set(guard, "1", nx=True, ex=30):
        return
    try:
        from workers.vercel_tasks import poll

        poll.delay()
    except Exception as exc:
        # The committed PostgreSQL job remains queued; a later document poll retries dispatch.
        logger.error("queue_dispatch_failed", extra={"exception_type": type(exc).__name__})
        if recover and client:
            client.delete(guard)

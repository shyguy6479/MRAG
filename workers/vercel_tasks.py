"""Private, queue-triggered ingestion worker; no long-running process required."""

import sys
from pathlib import Path

from celery import Celery, Task
from vercel.integrations.celery import install_vercel_celery_integration

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# Keep the adapter visible to Vercel's import-based dependency bundler.
install_vercel_celery_integration()

app = Celery("mrag", broker="vercel://", backend="vercel-runtime-cache://")
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_queue="ingestion",
    broker_transport_options={"lease_duration": 300, "requeue_delay_seconds": 60},
)


@app.task(bind=True, name="mrag.ingest", max_retries=3, ignore_result=True)
def poll(task: Task) -> bool:
    from atlasrag.core.hosting import deployment_settings
    from atlasrag.core.runtime import Runtime
    from atlasrag.core.storage import Database
    from atlasrag.observability.telemetry import Telemetry

    settings = deployment_settings()
    db = Database(settings)
    telemetry = Telemetry(settings.otlp_endpoint)
    runtime = None
    try:
        db.initialize()
        runtime = Runtime(db, settings, telemetry)
        processed = runtime.ingestion.process_one()
        if processed:
            # Each invocation handles one durable job, then wakes the next one.
            poll.delay()
        return processed
    except Exception:
        # Provider errors may contain credentials; only a safe error reaches Celery logs.
        raise task.retry(exc=RuntimeError("Ingestion worker unavailable"), countdown=5) from None
    finally:
        if runtime is not None:
            runtime.close()
        db.close()
        telemetry.close()

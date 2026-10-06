from functools import lru_cache

from celery import Celery

from atlasrag.core.config import Settings
from atlasrag.core.runtime import Runtime
from atlasrag.core.storage import Database
from atlasrag.observability.telemetry import Telemetry, configure_logging

settings = Settings()
app = Celery("atlasrag", broker=settings.redis_url)
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=90,
    task_time_limit=120,
    timezone="UTC",
    beat_schedule={"recover-durable-jobs": {"task": "atlasrag.poll", "schedule": 3.0}},
)


@lru_cache(maxsize=1)
def runtime() -> Runtime:
    configure_logging(settings.log_level)
    db = Database(settings)
    db.initialize()
    return Runtime(db, settings, Telemetry(settings.otlp_endpoint))


@app.task(name="atlasrag.poll")
def poll() -> bool:
    service = runtime()
    try:
        return service.ingestion.process_one()
    finally:
        if service.cache.client:
            service.cache.client.setex("atlas:worker:heartbeat", 150, "alive")

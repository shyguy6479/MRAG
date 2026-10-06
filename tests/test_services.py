import os

import pytest
from alembic import command
from alembic.config import Config

from atlasrag.core.cache import CacheStore
from atlasrag.core.config import Settings
from atlasrag.core.models import DocumentCreate
from atlasrag.core.storage import Database
from atlasrag.ingestion.service import IngestionService
from atlasrag.observability.telemetry import Telemetry


@pytest.mark.integration
def test_postgres_and_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    url = os.environ.get("ATLAS_INTEGRATION_DATABASE_URL")
    redis_url = os.environ.get("ATLAS_INTEGRATION_REDIS_URL")
    if not url or not redis_url:
        pytest.skip("PostgreSQL / Redis integration URLs are not configured")
    monkeypatch.setenv("ATLAS_DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    settings = Settings(database_url=url, redis_url=redis_url, _env_file=None)
    db = Database(settings)
    db.initialize()
    telemetry = Telemetry()
    cache = CacheStore(settings, telemetry)
    assert db.ping() and cache.client is not None and cache.client.ping()
    doc = IngestionService(db, settings).submit(
        DocumentCreate(
            title="Integration fixture",
            content=(
                "PostgreSQL stores durable jobs while Redis caches "
                "deterministic intermediate results."
            ),
        )
    )
    try:
        assert IngestionService(db, settings).process_one()
        assert db.document(doc.id)[0].status == "ready"
        key = f"integration:{doc.id}"
        cache.set(key, "value", 30)
        assert cache.get(key) == "value"
        cache.client.delete(key)
    finally:
        db.delete(doc.id)
        cache.close()
        db.close()
        telemetry.close()

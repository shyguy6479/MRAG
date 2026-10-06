from atlasrag.agents.runner import Agent
from atlasrag.core.cache import CacheStore
from atlasrag.core.config import Settings
from atlasrag.core.storage import Database
from atlasrag.ingestion.service import IngestionService
from atlasrag.observability.telemetry import Telemetry
from atlasrag.retrieval.engine import RetrievalEngine


class Runtime:
    def __init__(self, db: Database, settings: Settings, telemetry: Telemetry) -> None:
        self.cache = CacheStore(settings, telemetry)
        self.engine = RetrievalEngine(db, settings, self.cache, telemetry)
        self.ingestion = IngestionService(
            db, settings, index_writer=self.engine.qdrant.upsert if self.engine.qdrant else None
        )
        self.agent = Agent(self.engine, settings, telemetry)

    def close(self) -> None:
        self.cache.close()
        if self.engine.qdrant:
            self.engine.qdrant.client.close()

import json
import logging
import threading
from dataclasses import dataclass
from time import perf_counter

from atlasrag.core.cache import CacheStore, cache_key
from atlasrag.core.config import Settings
from atlasrag.core.models import Evidence, Filters, SearchHit
from atlasrag.core.protocols import DenseIndex, Reranker
from atlasrag.core.storage import Database
from atlasrag.observability.telemetry import Telemetry
from atlasrag.reranking.rerankers import CrossEncoderReranker, LexicalReranker
from atlasrag.retrieval.fusion import reciprocal_rank_fusion
from atlasrag.retrieval.indexes import BM25Index, LSAIndex

logger = logging.getLogger("atlasrag.retrieval")


@dataclass(frozen=True)
class Snapshot:
    revision: int
    evidence: list[Evidence]
    dense: DenseIndex
    sparse: BM25Index


@dataclass
class SearchResult:
    hits: list[SearchHit]
    considered: int
    cache_hit: bool
    warnings: list[str]


def filter_evidence(evidence: list[Evidence], filters: Filters) -> list[Evidence]:
    ids = set(filters.document_ids)
    tags = set(filters.tags)
    return [
        e
        for e in evidence
        if (not ids or e.document_id in ids)
        and (not tags or tags.issubset(set(e.tags)))
        and (not filters.section or filters.section.casefold() in e.section.casefold())
    ]


class RetrievalEngine:
    def __init__(
        self, db: Database, settings: Settings, cache: CacheStore, telemetry: Telemetry
    ) -> None:
        self.db, self.settings, self.cache, self.telemetry = db, settings, cache, telemetry
        self.lock = threading.RLock()
        self.current: Snapshot | None = None
        self.embedder = None
        self.qdrant = None
        if settings.dense_backend == "neural":
            from atlasrag.providers.neural import NeuralEmbedder, QdrantIndex

            self.embedder = NeuralEmbedder(settings, cache)
            if settings.vector_backend == "qdrant":
                self.qdrant = QdrantIndex(settings, self.embedder)
        self.reranker: Reranker = (
            CrossEncoderReranker(settings, cache)
            if settings.reranker == "cross_encoder"
            else LexicalReranker()
        )

    def snapshot(self) -> Snapshot:
        with self.lock:
            if self.current and self.current.revision == self.db.revision():
                return self.current
            revision, evidence = self.db.snapshot()
            dense: DenseIndex
            with self.telemetry.stage("embedding_index"):
                if self.qdrant:
                    dense = self.qdrant
                elif self.embedder:
                    from atlasrag.providers.neural import NeuralMemoryIndex

                    dense = NeuralMemoryIndex(evidence, self.embedder)
                else:
                    dense = LSAIndex(evidence)
                self.current = Snapshot(revision, evidence, dense, BM25Index(evidence))
            return self.current

    def search(
        self, snapshot: Snapshot, query: str, filters: Filters, strategy: str, top_k: int
    ) -> SearchResult:
        settings = self.settings
        key = cache_key(
            "retrieval",
            [
                snapshot.revision,
                query,
                filters.model_dump(mode="json"),
                strategy,
                top_k,
                settings.dense_backend,
                settings.embedding_model,
                settings.embedding_revision,
                self.reranker.identity,
                settings.dense_top_k,
                settings.sparse_top_k,
                settings.rrf_k,
            ],
        )
        cached = self.cache.get(key)
        if cached:
            data = json.loads(cached)
            self.telemetry.cache_saved.inc(data["duration_seconds"])
            return SearchResult(
                [SearchHit.model_validate(h) for h in data["hits"]],
                data["considered"],
                True,
                data["warnings"],
            )
        started = perf_counter()
        allowed = filter_evidence(snapshot.evidence, filters)
        warnings: list[str] = []
        with self.telemetry.stage("retrieval"):
            dense = (
                snapshot.dense.search(query, allowed, settings.dense_top_k)
                if strategy != "sparse"
                else []
            )
            sparse = (
                snapshot.sparse.search(query, allowed, settings.sparse_top_k)
                if strategy != "dense"
                else []
            )
            hits = (
                dense
                if strategy == "dense"
                else sparse
                if strategy == "sparse"
                else reciprocal_rank_fusion([dense, sparse], settings.rrf_k)
            )
        considered = len(hits)
        self.telemetry.candidates.inc(considered)
        if strategy in {"hybrid_reranked", "agentic"}:
            try:
                with self.telemetry.stage("reranking"):
                    hits = self.reranker.rerank(query, hits, top_k)
            except Exception as exc:
                logger.warning("reranker_degraded", extra={"exception_type": type(exc).__name__})
                warnings.append("Reranking failed; hybrid ranking was used.")
                hits = hits[:top_k]
        else:
            hits = hits[:top_k]
        # Do not cache a degraded result; a healthy reranker may recover next request.
        if not warnings:
            self.cache.set(
                key,
                json.dumps(
                    {
                        "hits": [h.model_dump(mode="json") for h in hits],
                        "considered": considered,
                        "warnings": warnings,
                        "duration_seconds": perf_counter() - started,
                    }
                ),
            )
        return SearchResult(hits, considered, False, warnings)

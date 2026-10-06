import json
import threading

from atlasrag.core.cache import CacheStore, cache_key
from atlasrag.core.config import Settings
from atlasrag.core.models import SearchHit
from atlasrag.retrieval.text import tokens


class LexicalReranker:
    identity = "lexical-coverage-v1"

    def rerank(self, query: str, hits: list[SearchHit], top_k: int) -> list[SearchHit]:
        terms = set(tokens(query))
        reranked = []
        for rank, hit in enumerate(hits):
            body = set(tokens(hit.evidence.text))
            title = set(tokens(hit.evidence.title + " " + hit.evidence.section))
            coverage = len(terms & body) / max(len(terms), 1)
            score = (
                0.8 * coverage + 0.15 * len(terms & title) / max(len(terms), 1) + 0.05 / (rank + 1)
            )
            reranked.append(hit.model_copy(update={"rerank_score": score}))
        return sorted(
            reranked, key=lambda h: (-float(h.rerank_score or 0), str(h.evidence.chunk_id))
        )[:top_k]


class CrossEncoderReranker:
    def __init__(self, settings: Settings, cache: CacheStore) -> None:
        from sentence_transformers import CrossEncoder

        self.identity = f"{settings.reranker_model}@{settings.reranker_revision or 'default'}"
        self.model = CrossEncoder(settings.reranker_model, revision=settings.reranker_revision)
        self.cache, self.lock = cache, threading.RLock()

    def rerank(self, query: str, hits: list[SearchHit], top_k: int) -> list[SearchHit]:
        if not hits:
            return []
        key = cache_key("rerank", [self.identity, query, [h.evidence.text for h in hits]])
        cached = self.cache.get(key)
        if cached:
            scores = json.loads(cached)
        else:
            with self.lock:
                scores = self.model.predict([(query, hit.evidence.text) for hit in hits]).tolist()
            self.cache.set(key, json.dumps(scores))
        result = [
            h.model_copy(update={"rerank_score": float(s)})
            for h, s in zip(hits, scores, strict=True)
        ]
        return sorted(
            result, key=lambda h: (-float(h.rerank_score or 0), str(h.evidence.chunk_id))
        )[:top_k]

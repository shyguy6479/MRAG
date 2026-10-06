import hashlib
import json
import math
import threading
from collections.abc import Sequence
from typing import Any

import numpy as np

from atlasrag.core.cache import CacheStore, cache_key
from atlasrag.core.config import Settings
from atlasrag.core.models import Evidence, SearchHit


class NeuralEmbedder:
    def __init__(self, settings: Settings, cache: CacheStore) -> None:
        from sentence_transformers import SentenceTransformer

        self.identity = f"{settings.embedding_model}@{settings.embedding_revision or 'default'}"
        self.model = SentenceTransformer(
            settings.embedding_model, revision=settings.embedding_revision
        )
        self.cache, self.lock = cache, threading.RLock()

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[Any] = [None] * len(texts)
        missing = []
        keys = [cache_key("embedding", [self.identity, text]) for text in texts]
        for i, key in enumerate(keys):
            value = self.cache.get(key)
            if value:
                vectors[i] = json.loads(value)
            else:
                missing.append(i)
        if missing:
            with self.lock:
                encoded = self.model.encode(
                    [texts[i] for i in missing], normalize_embeddings=True, batch_size=32
                ).tolist()
            for i, vector in zip(missing, encoded, strict=True):
                vectors[i] = vector
                self.cache.set(keys[i], json.dumps(vector))
        return vectors


class NeuralMemoryIndex:
    def __init__(self, evidence: Sequence[Evidence], embedder: NeuralEmbedder) -> None:
        self.evidence, self.embedder = list(evidence), embedder
        self.matrix = np.asarray(embedder.encode([e.text for e in evidence]))

    def search(self, query: str, allowed: Sequence[Evidence], top_k: int) -> list[SearchHit]:
        if not self.evidence:
            return []
        vector = np.asarray(self.embedder.encode([query])[0])
        scores = self.matrix @ vector
        ids = {e.chunk_id for e in allowed}
        hits = [
            SearchHit(evidence=e, score=float(s), dense_score=float(s))
            for e, s in zip(self.evidence, scores, strict=True)
            if e.chunk_id in ids
        ]
        return sorted(hits, key=lambda h: (-h.score, str(h.evidence.chunk_id)))[:top_k]


class QdrantIndex:
    def __init__(self, settings: Settings, embedder: NeuralEmbedder) -> None:
        from qdrant_client import QdrantClient

        self.client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_key.get_secret_value() or None,
            timeout=math.ceil(settings.provider_timeout_seconds),
        )
        digest = hashlib.sha256(embedder.identity.encode()).hexdigest()[:12]
        self.collection = f"{settings.qdrant_collection}_{digest}"
        self.embedder, self.lock = embedder, threading.RLock()

    def upsert(self, evidence: list[Evidence]) -> None:
        from qdrant_client import models

        if not evidence:
            return
        vectors = self.embedder.encode([e.text for e in evidence])
        with self.lock:
            if not self.client.collection_exists(self.collection):
                try:
                    self.client.create_collection(
                        self.collection,
                        vectors_config=models.VectorParams(
                            size=len(vectors[0]), distance=models.Distance.COSINE
                        ),
                    )
                except Exception:
                    # Another worker may create the same collection concurrently.
                    if not self.client.collection_exists(self.collection):
                        raise
            self.client.upsert(
                self.collection,
                wait=True,
                points=[
                    models.PointStruct(
                        id=str(e.chunk_id), vector=v, payload={"document_id": str(e.document_id)}
                    )
                    for e, v in zip(evidence, vectors, strict=True)
                ],
            )

    def search(self, query: str, allowed: Sequence[Evidence], top_k: int) -> list[SearchHit]:
        from qdrant_client import models

        if not allowed:
            return []
        by_id = {str(e.chunk_id): e for e in allowed}
        result = self.client.query_points(
            self.collection,
            query=self.embedder.encode([query])[0],
            limit=top_k,
            query_filter=models.Filter(must=[models.HasIdCondition(has_id=list(by_id))]),
        )
        return [
            SearchHit(evidence=by_id[str(point.id)], score=point.score, dense_score=point.score)
            for point in result.points
            if str(point.id) in by_id
        ]

    def delete_document(self, document_id: str) -> None:
        from qdrant_client import models

        if self.client.collection_exists(self.collection):
            self.client.delete(
                self.collection,
                wait=True,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="document_id", match=models.MatchValue(value=document_id)
                            )
                        ]
                    )
                ),
            )

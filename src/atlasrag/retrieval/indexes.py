import math
from collections import Counter
from collections.abc import Sequence

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from atlasrag.core.models import Evidence, SearchHit
from atlasrag.retrieval.text import tokens


class BM25Index:
    """Positive Robertson IDF; deterministic BM25 implementation."""

    def __init__(self, evidence: Sequence[Evidence], k1: float = 1.5, b: float = 0.75) -> None:
        self.evidence, self.k1, self.b = list(evidence), k1, b
        self.counts = [Counter(tokens(f"{e.title} {e.section} {e.text}")) for e in evidence]
        self.lengths = [sum(c.values()) for c in self.counts]
        self.average = sum(self.lengths) / max(len(self.lengths), 1)
        frequencies: Counter[str] = Counter()
        for counts in self.counts:
            frequencies.update(counts.keys())
        self.idf = {
            term: math.log1p((len(evidence) - df + 0.5) / (df + 0.5))
            for term, df in frequencies.items()
        }

    def search(self, query: str, allowed: Sequence[Evidence], top_k: int) -> list[SearchHit]:
        ids = {e.chunk_id for e in allowed}
        results = []
        terms = set(tokens(query))
        for evidence, counts, length in zip(self.evidence, self.counts, self.lengths, strict=True):
            if evidence.chunk_id not in ids:
                continue
            score = 0.0
            for term in terms:
                frequency = counts.get(term, 0)
                denominator = frequency + self.k1 * (
                    1 - self.b + self.b * length / (self.average or 1)
                )
                score += self.idf.get(term, 0) * frequency * (self.k1 + 1) / denominator
            if score > 0:
                results.append(SearchHit(evidence=evidence, score=score, sparse_score=score))
        return sorted(results, key=lambda hit: (-hit.score, str(hit.evidence.chunk_id)))[:top_k]


class LSAIndex:
    """Corpus-fitted dense baseline; never represented as a neural model."""

    def __init__(self, evidence: Sequence[Evidence]) -> None:
        self.evidence = list(evidence)
        self.vectorizer = TfidfVectorizer(
            tokenizer=tokens,
            token_pattern=None,
            lowercase=False,
            max_features=20000,
            sublinear_tf=True,
        )
        self.svd: TruncatedSVD | None = None
        self.empty = not evidence or not any(tokens(e.text + " " + e.title) for e in evidence)
        if self.empty:
            self.matrix = np.empty((0, 0))
            return
        sparse = self.vectorizer.fit_transform(
            [f"{e.title} {e.section} {e.text}" for e in evidence]
        )
        dimensions = min(128, sparse.shape[0] - 1, sparse.shape[1] - 1)
        if dimensions >= 2:
            self.svd = TruncatedSVD(n_components=dimensions, random_state=42)
            self.matrix = normalize(self.svd.fit_transform(sparse))
        else:
            self.matrix = normalize(sparse.toarray())

    def search(self, query: str, allowed: Sequence[Evidence], top_k: int) -> list[SearchHit]:
        if self.empty:
            return []
        vector = self.vectorizer.transform([query])
        dense = normalize(self.svd.transform(vector) if self.svd else vector.toarray())
        scores = (self.matrix @ dense.T).ravel()
        ids = {e.chunk_id for e in allowed}
        results = [
            SearchHit(evidence=e, score=float(s), dense_score=float(s))
            for e, s in zip(self.evidence, scores, strict=True)
            if e.chunk_id in ids and s > 0.05
        ]
        return sorted(results, key=lambda hit: (-hit.score, str(hit.evidence.chunk_id)))[:top_k]

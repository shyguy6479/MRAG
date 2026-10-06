import math
from collections.abc import Sequence

from atlasrag.core.models import SearchHit


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[SearchHit]],
    k: int = 60,
    weights: Sequence[float] | None = None,
    top_k: int | None = None,
) -> list[SearchHit]:
    """RRF(d) = sum_j weight_j / (k + one_based_rank_j(d))."""
    if k < 1 or (top_k is not None and top_k < 1):
        raise ValueError("k and top_k must be positive")
    weights = list(weights) if weights is not None else [1.0] * len(rankings)
    if len(weights) != len(rankings) or any(w < 0 or not math.isfinite(w) for w in weights):
        raise ValueError("provide one finite non-negative weight per ranking")
    merged: dict[str, SearchHit] = {}
    for ranking, weight in zip(rankings, weights, strict=True):
        if weight == 0:
            continue
        seen: set[str] = set()
        rank = 0
        for hit in ranking:
            key = str(hit.evidence.chunk_id)
            if key in seen:
                continue
            seen.add(key)
            rank += 1
            if key not in merged:
                merged[key] = hit.model_copy(update={"score": 0.0})
            current = merged[key]
            current.score += weight / (k + rank)
            if hit.dense_score is not None:
                current.dense_score = hit.dense_score
            if hit.sparse_score is not None:
                current.sparse_score = hit.sparse_score
    return sorted(merged.values(), key=lambda hit: (-hit.score, str(hit.evidence.chunk_id)))[:top_k]

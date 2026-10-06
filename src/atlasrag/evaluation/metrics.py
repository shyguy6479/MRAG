import math
from collections import Counter

from atlasrag.retrieval.text import tokens


def retrieval_metrics(ranked: list[str], relevant: set[str], k: int) -> dict[str, float]:
    if k < 1:
        raise ValueError("k must be positive")
    unique = list(dict.fromkeys(ranked))[:k]
    gains = [float(item in relevant) for item in unique]
    found = sum(gains)
    dcg = sum(gain / math.log2(rank + 2) for rank, gain in enumerate(gains))
    ideal = sum(1 / math.log2(rank + 2) for rank in range(min(k, len(relevant))))
    return {
        f"recall_at_{k}": found / len(relevant) if relevant else 0,
        f"precision_at_{k}": found / k,
        "mrr": next((1 / (rank + 1) for rank, value in enumerate(gains) if value), 0),
        f"ndcg_at_{k}": dcg / ideal if ideal else 0,
    }


def token_f1(candidate: str, reference: str) -> float:
    left, right = Counter(tokens(candidate)), Counter(tokens(reference))
    overlap = sum((left & right).values())
    if not overlap:
        return 0.0
    precision, recall = overlap / sum(left.values()), overlap / sum(right.values())
    return 2 * precision * recall / (precision + recall)

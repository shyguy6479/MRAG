import math

import pytest

from atlasrag.evaluation.metrics import retrieval_metrics, token_f1


def test_metrics_against_hand_calculated_ranking() -> None:
    result = retrieval_metrics(["a", "b", "b", "c"], {"b", "c"}, 3)
    assert result["recall_at_3"] == 1
    assert result["precision_at_3"] == pytest.approx(2 / 3)
    assert result["mrr"] == 0.5
    assert result["ndcg_at_3"] == pytest.approx((1 / math.log2(3) + 0.5) / (1 + 1 / math.log2(3)))


def test_metrics_empty_and_short_rankings() -> None:
    assert retrieval_metrics([], {"a"}, 5)["recall_at_5"] == 0
    assert retrieval_metrics(["a"], {"a"}, 5)["precision_at_5"] == 0.2
    assert retrieval_metrics(["a"], set(), 5)["ndcg_at_5"] == 0
    assert token_f1("memory cache", "memory cache") == 1
    assert token_f1("", "reference") == 0

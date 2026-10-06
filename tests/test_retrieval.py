from datetime import UTC, datetime
from uuid import UUID

import pytest

from atlasrag.core.models import Evidence, Filters, SearchHit
from atlasrag.reranking.rerankers import LexicalReranker
from atlasrag.retrieval.engine import filter_evidence
from atlasrag.retrieval.fusion import reciprocal_rank_fusion
from atlasrag.retrieval.indexes import BM25Index, LSAIndex


def evidence(number: int, text: str, doc: int | None = None) -> Evidence:
    return Evidence(
        chunk_id=UUID(int=number),
        document_id=UUID(int=doc or number),
        title=f"Study {number}",
        source="test",
        section="Results",
        text=text,
        ordinal=0,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        tags=("research",),
    )


def hit(number: int) -> SearchHit:
    return SearchHit(evidence=evidence(number, f"Passage {number}"), score=99)


def test_rrf_known_ranks_duplicates_and_no_mutation() -> None:
    a, b, c = hit(1), hit(2), hit(3)
    result = reciprocal_rank_fusion([[a, a, b], [b, c]], k=60)
    assert result[0].evidence.chunk_id == b.evidence.chunk_id
    assert result[0].score == pytest.approx(1 / 62 + 1 / 61)
    assert a.score == 99
    assert len(result) == 3


def test_rrf_ties_empty_weights_and_limits() -> None:
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[hit(2)], [hit(1)]])[0].evidence.chunk_id == UUID(int=1)
    assert len(reciprocal_rank_fusion([[hit(1), hit(2)]], top_k=1)) == 1
    assert reciprocal_rank_fusion([[hit(1)]], weights=[0]) == []
    for weights in [[], [-1], [float("nan")]]:
        with pytest.raises(ValueError):
            reciprocal_rank_fusion([[hit(1)]], weights=weights)


@pytest.mark.parametrize("index_type", [BM25Index, LSAIndex])
def test_retrieval_and_filtering(index_type: type) -> None:
    corpus = [
        evidence(1, "Paged attention allocates KV cache in memory blocks."),
        evidence(2, "Quantization stores model weights in four bit integers."),
        evidence(3, "Speculative decoding uses a draft model to propose tokens."),
    ]
    index = index_type(corpus)
    assert index.search("four bit weight quantization", corpus, 3)[0].evidence.chunk_id == UUID(
        int=2
    )
    limited = filter_evidence(corpus, Filters(document_ids=[UUID(int=1)]))
    assert all(h.evidence.document_id == UUID(int=1) for h in index.search("model", limited, 3))
    assert filter_evidence(corpus, Filters(tags=["private"])) == []
    assert index.search("xyzzyplugh", corpus, 3) == []


def test_lexical_reranker_reorders_actual_evidence() -> None:
    hits = [
        SearchHit(evidence=evidence(1, "Memory allocation uses blocks."), score=1),
        SearchHit(evidence=evidence(2, "Quantization reduces model weight memory."), score=0.5),
    ]
    ranked = LexicalReranker().rerank("quantization weight memory", hits, 2)
    assert ranked[0].evidence.chunk_id == UUID(int=2)


def test_empty_indexes() -> None:
    assert LSAIndex([]).search("query", [], 5) == []
    assert BM25Index([]).search("query", [], 5) == []

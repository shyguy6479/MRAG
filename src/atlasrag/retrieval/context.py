import re

from atlasrag.core.models import Citation, SearchHit
from atlasrag.retrieval.text import token_bound, tokens


def select_context(hits: list[SearchHit], budget: int, max_chunks: int) -> list[Citation]:
    """Greedy document diversity, duplicate rejection and a conservative byte budget."""
    if budget < 1 or max_chunks < 1:
        return []
    pending = list(hits)
    selected: list[Citation] = []
    used_documents: set[str] = set()
    used_chunks: set[str] = set()
    sets: list[set[str]] = []
    remaining = budget
    while pending and len(selected) < max_chunks:
        # Cover distinct documents first, preserving relevance order within each group.
        index = next(
            (i for i, h in enumerate(pending) if str(h.evidence.document_id) not in used_documents),
            0,
        )
        hit = pending.pop(index)
        evidence = hit.evidence
        terms = set(tokens(evidence.text))
        if str(evidence.chunk_id) in used_chunks:
            continue
        if any(len(terms & previous) / max(len(terms | previous), 1) > 0.82 for previous in sets):
            continue
        overhead = token_bound(evidence.title + evidence.section) + 32
        available = remaining - overhead
        if available < 100:
            continue
        text = evidence.text
        if token_bound(text) > available:
            text = text.encode()[:available].decode("utf-8", errors="ignore")
            # Avoid an incomplete final word. This remains an exact prefix of the chunk.
            text = text.rsplit(" ", 1)[0].rstrip()
            boundaries = list(re.finditer(r"[.!?](?:\s|$)", text))
            if not boundaries:
                continue
            text = text[: boundaries[-1].start() + 1]
        if len(text) < 40:
            continue
        remaining -= token_bound(text) + overhead
        selected.append(
            Citation(
                number=len(selected) + 1,
                document_id=evidence.document_id,
                chunk_id=evidence.chunk_id,
                title=evidence.title,
                source=evidence.source,
                section=evidence.section,
                page=evidence.page,
                text=text,
                retrieval_score=hit.score,
            )
        )
        used_documents.add(str(evidence.document_id))
        used_chunks.add(str(evidence.chunk_id))
        sets.append(terms)
    return selected

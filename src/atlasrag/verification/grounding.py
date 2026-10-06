import re
from typing import Literal

from atlasrag.core.models import Citation, Claim
from atlasrag.retrieval.text import tokens

INJECTION = re.compile(
    r"ignore (?:all |the |any )?(?:previous|prior|system)|system prompt|"
    r"you are (?:now |an? )|reveal.*(?:secret|key|password)|"
    r"execute (?:this|the following)|<\|(?:system|assistant)|"
    r"(?:send|post).*api.?key",
    re.I,
)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def verify_claims(answer: str, citations: list[Citation], threshold: float = 0.65) -> list[Claim]:
    by_number = {c.number: c for c in citations}
    claims = []
    for line in answer.splitlines():
        line = line.strip().removeprefix("- ")
        if not line or line.startswith("#") or line.startswith("Evidence from the indexed"):
            continue
        if line.startswith("The indexed documents do not provide enough evidence"):
            continue
        refs = [int(n) for n in re.findall(r"\[(\d+)\]", line)]
        text = re.sub(r"\[\d+\]", "", line).strip().strip('“”" ')
        terms = set(tokens(text))
        score = 0.0
        exact = False
        for number in refs:
            if number not in by_number:
                continue
            evidence = by_number[number].text
            if normalize(text) in normalize(evidence):
                score, exact = 1.0, True
                break
            coverage = len(terms & set(tokens(evidence))) / max(len(terms), 1)
            numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", text))
            if not numbers.issubset(set(re.findall(r"\b\d+(?:\.\d+)?\b", evidence))):
                coverage = 0
            # Lexical overlap alone is never accepted as proven semantic entailment.
            score = max(score, coverage)
        if not refs or any(ref not in by_number for ref in refs) or INJECTION.search(text):
            score, exact = 0.0, False
        status: Literal["supported", "partially_supported", "unsupported"] = (
            "supported" if exact else "partially_supported" if score >= threshold else "unsupported"
        )
        claims.append(Claim(text=text, status=status, score=score, citation_numbers=refs))
    return claims

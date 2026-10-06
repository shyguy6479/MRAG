from collections.abc import Sequence
from typing import Protocol

from atlasrag.core.models import Citation, Claim, Evidence, Generation, SearchHit


class Embedder(Protocol):
    @property
    def identity(self) -> str: ...
    def encode(self, texts: Sequence[str]) -> list[list[float]]: ...


class DenseIndex(Protocol):
    def search(self, query: str, allowed: Sequence[Evidence], top_k: int) -> list[SearchHit]: ...


class Reranker(Protocol):
    @property
    def identity(self) -> str: ...
    def rerank(self, query: str, hits: list[SearchHit], top_k: int) -> list[SearchHit]: ...


class Generator(Protocol):
    async def generate(self, question: str, citations: list[Citation]) -> Generation: ...


class Verifier(Protocol):
    def verify(self, answer: str, citations: list[Citation]) -> list[Claim]: ...


class Cache(Protocol):
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str, ttl_seconds: int) -> None: ...
    def close(self) -> None: ...

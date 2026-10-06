from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utcnow() -> datetime:
    return datetime.now(UTC)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class DocumentStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class DocumentCreate(Contract):
    title: str = Field(min_length=1, max_length=250)
    content: str = Field(min_length=1, max_length=2_000_000)
    source: str = Field(default="manual", max_length=1000)
    format: Literal["md", "txt", "html"] = "md"
    chunking: Literal["fixed", "recursive", "semantic"] = "semantic"
    tags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("title", "content")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()

    @field_validator("tags")
    @classmethod
    def valid_tags(cls, value: list[str]) -> list[str]:
        if any(not t.strip() or len(t) > 60 for t in value):
            raise ValueError("tags must contain 1–60 characters")
        return sorted(set(value))


class DocumentInfo(Contract):
    id: UUID
    title: str
    source: str
    format: str
    status: DocumentStatus
    chunking: str
    tags: list[str]
    created_at: datetime
    chunk_count: int = 0
    error: str | None = None


class Evidence(Contract):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    chunk_id: UUID
    document_id: UUID
    title: str
    source: str
    section: str
    page: int | None = Field(default=None, ge=1)
    text: str = Field(min_length=1)
    ordinal: int = Field(ge=0)
    created_at: datetime
    tags: tuple[str, ...] = ()


class SearchHit(Contract):
    evidence: Evidence
    score: float
    dense_score: float | None = None
    sparse_score: float | None = None
    rerank_score: float | None = None


class Filters(Contract):
    document_ids: list[UUID] = Field(default_factory=list, max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=20)
    section: str | None = Field(default=None, max_length=200)


class QueryRequest(Contract):
    question: str = Field(min_length=1, max_length=4000)
    filters: Filters = Field(default_factory=Filters)
    strategy: Literal["dense", "sparse", "hybrid", "hybrid_reranked", "agentic"] = "agentic"
    top_k: int = Field(default=6, ge=1, le=20)
    rewrite: bool = True
    decompose: bool = True
    verify: bool = True

    @field_validator("question")
    @classmethod
    def valid_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must not be blank")
        return value.strip()


class ChatRequest(QueryRequest):
    conversation_id: UUID | None = None


class Citation(Contract):
    number: int = Field(ge=1)
    document_id: UUID
    chunk_id: UUID
    title: str
    source: str
    section: str
    page: int | None
    text: str
    retrieval_score: float


class TraceStep(Contract):
    step: int
    action: str
    detail: str
    duration_ms: float
    evidence_ids: list[UUID] = Field(default_factory=list)


class Claim(Contract):
    text: str
    status: Literal["supported", "partially_supported", "unsupported"]
    score: float = Field(ge=0, le=1)
    citation_numbers: list[int]


class RetrievalInfo(Contract):
    strategy: str
    chunks_considered: int
    chunks_used: int
    corpus_revision: int
    queries: list[str]
    cache_hit: bool
    dense_backend: str
    reranker: str


class QueryResponse(Contract):
    id: UUID = Field(default_factory=uuid4)
    conversation_id: UUID | None = None
    answer: str
    citations: list[Citation]
    confidence: float = Field(ge=0, le=1)
    confidence_kind: str = "heuristic_evidence_support_not_probability"
    latency_ms: float
    retrieval: RetrievalInfo
    trace: list[TraceStep]
    claims: list[Claim]
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0
    generator: str
    warnings: list[str] = Field(default_factory=list)


class Generation(Contract):
    answer: str
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0


class ToolSpec(Contract):
    name: str
    description: str
    input_schema: dict[str, object]

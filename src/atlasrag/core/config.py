from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ATLAS_", extra="ignore")

    environment: Literal["local", "production", "test"] = "local"
    database_url: str = "sqlite:///data/atlas.db"
    redis_url: str | None = None
    api_key: SecretStr = SecretStr("")
    allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    ingestion_mode: Literal["local", "celery"] = "local"
    dense_backend: Literal["lsa", "neural"] = "lsa"
    vector_backend: Literal["memory", "qdrant"] = "memory"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_revision: str | None = None
    qdrant_url: str = "http://qdrant:6333"
    qdrant_key: SecretStr = SecretStr("")
    qdrant_collection: str = "atlas_chunks"
    reranker: Literal["lexical", "cross_encoder"] = "lexical"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_revision: str | None = None
    generator: Literal["extractive", "chat"] = "extractive"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = ""
    llm_key: SecretStr = SecretStr("")
    llm_free_inference: bool = False
    input_cost_per_million: float = Field(default=0, ge=0, allow_inf_nan=False)
    output_cost_per_million: float = Field(default=0, ge=0, allow_inf_nan=False)
    dense_top_k: int = Field(default=30, ge=1, le=100)
    sparse_top_k: int = Field(default=30, ge=1, le=100)
    final_top_k: int = Field(default=6, ge=1, le=20)
    rrf_k: int = Field(default=60, ge=1)
    chunk_size: int = Field(default=180, ge=30, le=1000)
    chunk_overlap: int = Field(default=30, ge=0)
    context_tokens: int = Field(default=2200, ge=128, le=16000)
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)
    max_documents: int = Field(default=200, ge=1, le=10000)
    max_chunks: int = Field(default=10000, ge=1)
    max_agent_steps: int = Field(default=16, ge=3, le=50)
    query_timeout_seconds: float = Field(default=45, gt=0, le=300)
    max_query_tokens: int = Field(default=24000, ge=100)
    max_output_tokens: int = Field(default=1000, ge=32, le=8000)
    max_query_cost: float = Field(default=0.10, gt=0, allow_inf_nan=False)
    provider_timeout_seconds: float = Field(default=15, gt=0, le=60)
    provider_retries: int = Field(default=2, ge=0, le=3)
    cache_ttl_seconds: int = Field(default=600, ge=1)
    cache_max_entries: int = Field(default=512, ge=1)
    rate_limit_per_minute: int = Field(default=60, ge=1)
    grounding_threshold: float = Field(default=0.65, ge=0, le=1)
    otlp_endpoint: str | None = None
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @model_validator(mode="after")
    def validate_combinations(self) -> Self:
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        if self.vector_backend == "qdrant" and self.dense_backend != "neural":
            raise ValueError("Qdrant requires stable neural embeddings; LSA is corpus-fitted")
        if self.ingestion_mode == "celery" and not self.redis_url:
            raise ValueError("Celery requires redis_url")
        if self.generator == "chat" and not self.llm_model:
            raise ValueError("chat generation requires llm_model")
        if (
            self.generator == "chat"
            and not self.llm_free_inference
            and self.input_cost_per_million + self.output_cost_per_million == 0
        ):
            raise ValueError(
                "configure provider pricing or explicitly declare free local inference"
            )
        if self.environment == "production":
            if len(self.api_key.get_secret_value()) < 32:
                raise ValueError("production requires an API key of at least 32 characters")
            if not self.database_url.startswith("postgresql+psycopg://"):
                raise ValueError("production requires PostgreSQL with psycopg")
            if not self.redis_url:
                raise ValueError("production requires Redis")
            if "*" in self.allowed_origins:
                raise ValueError("production disallows wildcard CORS")
            if self.dense_backend == "neural" and not self.embedding_revision:
                raise ValueError("production neural embeddings require a pinned revision")
            if self.reranker == "cross_encoder" and not self.reranker_revision:
                raise ValueError("production cross-encoder requires a pinned revision")
        return self

    def prepare_sqlite_directory(self) -> None:
        if self.database_url.startswith("sqlite:///"):
            path = self.database_url.removeprefix("sqlite:///")
            if path != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)

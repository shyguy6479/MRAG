"""Read-only presentation adapters for the research workspace.

No retrieval or generation algorithms are changed here. Existing route contracts
remain available. Benchmark IDs are allowlisted, never interpreted as paths.
"""

import asyncio
import json
from datetime import UTC
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

from fastapi import APIRouter, Request
from sqlalchemy import func, select

from atlasrag.core.errors import NotFound, ProviderUnavailable
from atlasrag.core.models import QueryRequest
from atlasrag.core.storage import MessageRow

router = APIRouter(tags=["workspace"])
RUN_FILES = {"local": "local.json", "neural": "neural.json"}


class SearchRequest(QueryRequest):
    strategy: Literal["dense", "sparse", "hybrid", "hybrid_reranked"] = "hybrid_reranked"


def benchmark_directory() -> Path:
    packaged = Path(__file__).resolve().parents[2] / "benchmarks"
    return packaged if packaged.exists() else Path("benchmarks")


@router.post("/search")
async def search(data: SearchRequest, request: Request) -> dict[str, Any]:
    engine = request.app.state.runtime.engine

    def run() -> dict[str, Any]:
        started = perf_counter()
        snapshot = engine.snapshot()
        result = engine.search(snapshot, data.question, data.filters, data.strategy, data.top_k)
        return {
            "query": data.question,
            "strategy": data.strategy,
            "hits": [hit.model_dump(mode="json") for hit in result.hits],
            "considered": result.considered,
            "cache_hit": result.cache_hit,
            "warnings": result.warnings,
            "latency_ms": (perf_counter() - started) * 1000,
            "corpus_revision": snapshot.revision,
            "dense_backend": engine.settings.dense_backend,
            "reranker": engine.settings.reranker,
        }

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(run), timeout=request.app.state.settings.query_timeout_seconds
        )
    except TimeoutError as exc:
        raise ProviderUnavailable() from exc


@router.get("/conversations")
async def conversations(request: Request) -> list[dict[str, Any]]:
    def read() -> list[dict[str, Any]]:
        ranked = select(
            MessageRow.conversation_id,
            MessageRow.question,
            MessageRow.response,
            MessageRow.created_at,
            func.count().over(partition_by=MessageRow.conversation_id).label("turn_count"),
            func.row_number()
            .over(
                partition_by=MessageRow.conversation_id,
                order_by=(MessageRow.created_at.desc(), MessageRow.id.desc()),
            )
            .label("position"),
        ).subquery()
        with request.app.state.db.sessions() as session:
            rows = session.execute(
                select(ranked)
                .where(ranked.c.position == 1)
                .order_by(ranked.c.created_at.desc(), ranked.c.conversation_id)
                .limit(50)
            ).mappings()
            return [
                {
                    "id": row["conversation_id"],
                    "title": row["question"],
                    "updated_at": (
                        row["created_at"]
                        if row["created_at"].tzinfo
                        else row["created_at"].replace(tzinfo=UTC)
                    ).isoformat(),
                    "sources": len(
                        {c["document_id"] for c in row["response"].get("citations", [])}
                    ),
                    "turns": row["turn_count"],
                    "response": row["response"],
                }
                for row in rows
            ]

    return await asyncio.to_thread(read)


@router.get("/evaluation-runs")
async def evaluation_runs() -> list[dict[str, Any]]:
    def read() -> list[dict[str, Any]]:
        runs = []
        for name, filename in RUN_FILES.items():
            path = benchmark_directory() / "results" / filename
            if not path.is_file():
                continue
            data = json.loads(path.read_text())
            runs.append(
                {
                    "id": name,
                    "measured_at": data["measured_at"],
                    "profile": data["profile"],
                    "pipelines": len(data["pipelines"]),
                    "questions": len({q["question_id"] for q in data["per_question"]}),
                }
            )
        return runs

    return await asyncio.to_thread(read)


@router.get("/evaluation-runs/{run_id}")
async def evaluation_run(run_id: str) -> dict[str, Any]:
    if run_id not in RUN_FILES:
        raise NotFound()
    path = benchmark_directory() / "results" / RUN_FILES[run_id]
    if not path.is_file():
        raise NotFound()
    data: dict[str, Any] = json.loads(await asyncio.to_thread(path.read_text))
    questions = benchmark_directory() / "questions.json"
    data["questions"] = (
        json.loads(await asyncio.to_thread(questions.read_text)) if questions.is_file() else []
    )
    return data

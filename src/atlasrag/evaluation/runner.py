import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import platform
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
from threadpoolctl import threadpool_limits

from atlasrag.agents.planning import plan_query
from atlasrag.core.config import Settings
from atlasrag.core.models import DocumentCreate, QueryRequest
from atlasrag.core.runtime import Runtime
from atlasrag.core.storage import Database
from atlasrag.evaluation.metrics import retrieval_metrics, token_f1
from atlasrag.observability.telemetry import Telemetry
from atlasrag.retrieval.fusion import reciprocal_rank_fusion
from atlasrag.verification.grounding import verify_claims


def percentiles(values: list[float]) -> dict[str, float]:
    return {f"p{p}_ms": round(float(np.percentile(values, p)), 3) for p in (50, 95, 99)}


async def run_experiments(root: Path, neural: bool = False) -> dict[str, Any]:
    config_path = root / "experiments/ablations.json"
    config = json.loads(config_path.read_text())
    questions_path = root / "benchmarks/questions.json"
    questions = json.loads(questions_path.read_text())
    corpus = sorted((root / "benchmarks/corpus").glob("*.md"))
    pins = json.loads((root / "configs/neural-models.json").read_text()) if neural else {}
    model_config = (
        {**pins, "dense_backend": "neural", "reranker": "cross_encoder"} if neural else {}
    )
    if neural:
        for pipeline in config["pipelines"]:
            pipeline["name"] = (
                pipeline["name"]
                .replace("Dense (LSA)", "Dense (MiniLM)")
                .replace("lexical reranker", "cross-encoder")
            )
    summaries, records = [], []
    for pipeline in config["pipelines"]:
        with tempfile.TemporaryDirectory(prefix="atlas-benchmark-") as folder:
            settings = Settings(
                environment="test",
                database_url=f"sqlite:///{folder}/benchmark.db",
                chunk_size=40,
                chunk_overlap=8,
                context_tokens=2200,
                log_level="ERROR",
                **model_config,
                _env_file=None,  # type: ignore[call-arg]
            )
            db = Database(settings)
            db.initialize()
            telemetry = Telemetry()
            runtime = Runtime(db, settings, telemetry)
            start = perf_counter()
            ids = {}
            for file in corpus:
                doc = runtime.ingestion.submit(
                    DocumentCreate(
                        title=file.stem,
                        content=file.read_text(),
                        source=f"authored-fixture/{file.name}",
                        chunking=pipeline.get("chunking", "semantic"),
                    )
                )
                ids[str(doc.id)] = file.stem
            runtime.ingestion.drain()
            ingestion_ms = (perf_counter() - start) * 1000
            if any(doc.status != "ready" for doc in db.documents()):
                raise RuntimeError("benchmark ingestion failed")
            start = perf_counter()
            snapshot = runtime.engine.snapshot()
            index_ms = (perf_counter() - start) * 1000
            latencies: list[float] = []
            cold: list[float] = []
            warm: list[float] = []
            rows: list[dict[str, Any]] = []
            for repetition in range(config["repetitions"]):
                for item in questions:
                    request = QueryRequest(
                        question=item["question"],
                        top_k=config["retrieval_k"],
                        strategy=pipeline["strategy"],
                        rewrite=pipeline.get("rewrite", True),
                        decompose=pipeline.get("decompose", True),
                        verify=pipeline.get("verify", True),
                    )
                    response = await runtime.agent.run(request, item.get("memory", []))
                    latencies.append(response.latency_ms)
                    (cold if repetition == 0 else warm).append(response.latency_ms)
                    if repetition != 0:
                        continue
                    plan = plan_query(
                        item["question"],
                        item.get("memory", []),
                        request.rewrite,
                        request.decompose and request.strategy == "agentic",
                    )
                    lists = [
                        runtime.engine.search(
                            snapshot, query, request.filters, request.strategy, 20
                        ).hits
                        for query in plan.queries
                    ]
                    hits = lists[0] if len(lists) == 1 else reciprocal_rank_fusion(lists)
                    ranked = list(dict.fromkeys(ids[str(hit.evidence.document_id)] for hit in hits))
                    metrics = retrieval_metrics(
                        ranked, set(item["relevant"]), config["retrieval_k"]
                    )
                    verified = verify_claims(response.answer, response.citations)
                    row = {
                        "pipeline": pipeline["name"],
                        "question_id": item["id"],
                        **metrics,
                        "token_f1_proxy": token_f1(response.answer, item["reference"]),
                        "exact_support_proxy": (
                            sum(c.status == "supported" for c in verified) / len(verified)
                            if verified
                            else 0
                        ),
                        "citation_validity": (
                            sum(
                                any(
                                    c.chunk_id == e.chunk_id and c.text in e.text
                                    for e in snapshot.evidence
                                )
                                for c in response.citations
                            )
                            / len(response.citations)
                            if response.citations
                            else 0
                        ),
                        "context_relevance": (
                            sum(
                                ids[str(c.document_id)] in item["relevant"]
                                for c in response.citations
                            )
                            / len(response.citations)
                            if response.citations
                            else 0
                        ),
                        "answer_relevance_proxy": token_f1(response.answer, item["question"]),
                        "latency_ms": response.latency_ms,
                        "ranked_documents": ranked[:5],
                        "answer": response.answer,
                        "tokens": response.input_tokens + response.output_tokens,
                        "cost_usd": response.estimated_cost_usd,
                        "chunks_used": response.retrieval.chunks_used,
                    }
                    rows.append(row)
                    records.append(row)
            metric_keys = [
                "recall_at_5",
                "precision_at_5",
                "mrr",
                "ndcg_at_5",
                "token_f1_proxy",
                "exact_support_proxy",
                "citation_validity",
                "context_relevance",
                "answer_relevance_proxy",
                "tokens",
                "cost_usd",
            ]
            summary: dict[str, Any] = {
                "name": pipeline["name"],
                "configuration": pipeline,
                **{
                    key: round(float(np.mean([row[key] for row in rows])), 6) for key in metric_keys
                },
                "latency": percentiles(latencies),
                "cold_latency": percentiles(cold),
                "warm_latency": percentiles(warm),
                "ingestion_ms": round(ingestion_ms, 3),
                "index_build_ms": round(index_ms, 3),
                "ingestion_documents_per_second": round(len(corpus) * 1000 / ingestion_ms, 3),
                "cache_hit_rate": runtime.cache.hits
                / max(runtime.cache.hits + runtime.cache.misses, 1),
                "chunks": len(snapshot.evidence),
                "queries_measured": len(latencies),
            }
            summaries.append(summary)
            print(
                f"{pipeline['name']}: recall@5={summary['recall_at_5']:.3f}, "
                f"cold P95={summary['cold_latency']['p95_ms']:.1f}ms",
                flush=True,
            )
            runtime.close()
            db.close()
            telemetry.close()
    from datetime import UTC, datetime

    return {
        "schema_version": 1,
        "measured_at": datetime.now(UTC).isoformat(),
        "profile": "neural + extractive" if neural else "LSA + lexical reranking + extractive",
        "scope": "8 authored notes / 12 questions; document-level relevance; in-process latency",
        "limitations": [
            "Small fixture authored with its questions; no generalization claim.",
            "Generation scores are lexical/exact-source proxies, not correctness judgments.",
            "Timing excludes HTTP/network transport and model loading; "
            "index build reported separately.",
            "Cache hit rate includes the retrieval metric pass "
            "and embedding/reranking cache operations.",
            "All generations are extractive: zero LLM tokens/cost, not free compute.",
        ],
        "corpus_sha256": hashlib.sha256(
            b"".join(p.name.encode() + p.read_bytes() for p in corpus)
        ).hexdigest(),
        "dataset_sha256": hashlib.sha256(questions_path.read_bytes()).hexdigest(),
        "experiment_configuration": config,
        "model_configuration": model_config,
        "chunk_size": 40,
        "chunk_overlap": 8,
        "context_budget_bytes": 2200,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": {
                name: importlib.metadata.version(name)
                for name in ["atlasrag", "numpy", "scikit-learn", "fastapi", "sqlalchemy"]
            },
        },
        "pipelines": summaries,
        "per_question": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--neural", action="store_true")
    args = parser.parse_args()
    root = Path.cwd()
    with threadpool_limits(limits=1):
        result = asyncio.run(run_experiments(root, args.neural))
    destination = root / "benchmarks/results"
    destination.mkdir(exist_ok=True)
    name = "neural.json" if args.neural else "local.json"
    (destination / name).write_text(json.dumps(result, indent=2) + "\n")
    if not args.neural:
        (destination / "latest.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"Saved {destination / name}")

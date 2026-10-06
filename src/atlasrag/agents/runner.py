import asyncio
import json
import re
from time import perf_counter

from atlasrag.agents.planning import plan_query
from atlasrag.agents.tools import DocumentTools, calculate
from atlasrag.core.budget import Budget
from atlasrag.core.config import Settings
from atlasrag.core.errors import BudgetExceeded
from atlasrag.core.models import (
    Citation,
    Generation,
    QueryRequest,
    QueryResponse,
    RetrievalInfo,
    SearchHit,
    TraceStep,
)
from atlasrag.generation.providers import INSUFFICIENT, ChatGenerator, ExtractiveGenerator
from atlasrag.observability.telemetry import Telemetry
from atlasrag.retrieval.context import select_context
from atlasrag.retrieval.engine import RetrievalEngine
from atlasrag.retrieval.fusion import reciprocal_rank_fusion
from atlasrag.verification.grounding import verify_claims


class Agent:
    def __init__(self, engine: RetrievalEngine, settings: Settings, telemetry: Telemetry) -> None:
        self.engine, self.settings, self.telemetry = engine, settings, telemetry
        self.generator = (
            ChatGenerator(settings) if settings.generator == "chat" else ExtractiveGenerator()
        )
        self.tools = DocumentTools(engine.db, engine)

    async def run(self, request: QueryRequest, memory: list[str] | None = None) -> QueryResponse:
        try:
            async with asyncio.timeout(self.settings.query_timeout_seconds):
                return await self._run(request, memory or [])
        except TimeoutError as exc:
            raise BudgetExceeded("query deadline reached") from exc

    async def _run(self, request: QueryRequest, memory: list[str]) -> QueryResponse:
        settings, telemetry = self.settings, self.telemetry
        started = perf_counter()
        budget = Budget(
            settings.max_agent_steps,
            settings.query_timeout_seconds,
            settings.max_query_tokens,
            settings.max_query_cost,
        )
        trace: list[TraceStep] = []
        warnings: list[str] = []

        def record(
            action: str, detail: str, since: float, hits: list[SearchHit] | None = None
        ) -> None:
            trace.append(
                TraceStep(
                    step=budget.steps,
                    action=action,
                    detail=detail,
                    duration_ms=round((perf_counter() - since) * 1000, 3),
                    evidence_ids=[h.evidence.chunk_id for h in hits or []],
                )
            )

        budget.step()
        mark = perf_counter()
        with telemetry.stage("query_analysis"):
            plan = plan_query(
                request.question,
                memory,
                request.rewrite,
                request.decompose and request.strategy == "agentic",
            )
        record("analyze", f"Intent: {plan.intent}", mark)
        if plan.rewritten != request.question:
            budget.step()
            with telemetry.stage("query_rewriting"):
                record("rewrite", plan.rewritten, perf_counter())
        if len(plan.queries) > 1:
            budget.step()
            record("decompose", f"{len(plan.queries)} bounded evidence queries", perf_counter())

        if plan.intent in {"conversation", "calculation"}:
            budget.step()
            mark = perf_counter()
            if plan.intent == "calculation":
                with telemetry.stage("tool_execution"):
                    value = calculate(plan.expression or "")
                telemetry.tools.labels(tool="calculator").inc()
                answer = f"{plan.expression} = {value:g}"
                action = "calculator"
            else:
                answer = (
                    "I can research your indexed documents, compare approaches, inspect sources, "
                    "and calculate arithmetic. Add documents, then ask a research question."
                )
                action = "direct_answer"
            record(action, "Completed without retrieval or an LLM call.", mark)
            return QueryResponse(
                answer=answer,
                citations=[],
                confidence=1,
                claims=[],
                confidence_kind="deterministic_tool_result"
                if action == "calculator"
                else "not_applicable",
                latency_ms=(perf_counter() - started) * 1000,
                trace=trace,
                generator="deterministic",
                retrieval=RetrievalInfo(
                    strategy="none",
                    chunks_considered=0,
                    chunks_used=0,
                    corpus_revision=self.engine.db.revision(),
                    queries=[],
                    cache_hit=False,
                    dense_backend=settings.dense_backend,
                    reranker=settings.reranker,
                ),
            )

        snapshot = await asyncio.to_thread(self.engine.snapshot)
        if plan.intent == "metadata":
            identifier = re.search(
                r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", request.question
            )
            if identifier:
                budget.step()
                mark = perf_counter()
                with telemetry.stage("tool_execution"):
                    info = await asyncio.to_thread(
                        self.tools.call,
                        "get_document_metadata",
                        {"document_id": identifier.group()},
                        snapshot,
                    )
                telemetry.tools.labels(tool="get_document_metadata").inc()
                record("get_document_metadata", "Read stored document metadata.", mark)
                return QueryResponse(
                    answer=info.model_dump_json(indent=2),
                    citations=[],
                    confidence=1,
                    confidence_kind="stored_metadata",
                    claims=[],
                    latency_ms=(perf_counter() - started) * 1000,
                    trace=trace,
                    generator="deterministic",
                    retrieval=RetrievalInfo(
                        strategy="metadata",
                        chunks_considered=0,
                        chunks_used=0,
                        corpus_revision=snapshot.revision,
                        queries=[],
                        cache_hit=False,
                        dense_backend=settings.dense_backend,
                        reranker=settings.reranker,
                    ),
                )

        rankings: list[list[SearchHit]] = []
        considered, cache_hits = 0, 0
        for query in plan.queries:
            budget.step()
            mark = perf_counter()
            result = await asyncio.to_thread(
                self.engine.search,
                snapshot,
                query,
                request.filters,
                request.strategy,
                min(20, request.top_k * 2),
            )
            telemetry.tools.labels(tool="search_documents").inc()
            rankings.append(result.hits)
            considered += result.considered
            cache_hits += result.cache_hit
            warnings.extend(result.warnings)
            record("search_documents", query, mark, result.hits)
        hits = (
            rankings[0] if len(rankings) == 1 else reciprocal_rank_fusion(rankings, settings.rrf_k)
        )
        budget.step()
        mark = perf_counter()
        with telemetry.stage("context_selection"):
            citations = select_context(hits, settings.context_tokens, request.top_k)
        record(
            "build_context",
            f"{len(citations)} distinct source chunks within the context budget.",
            mark,
        )

        async def generate(context: list[Citation]) -> Generation:
            budget.step()
            if isinstance(self.generator, ChatGenerator):
                # Reserve for every allowed attempt before any potentially billable call.
                prompt_bound = len(
                    json.dumps(self.generator.payload(plan.rewritten, context)).encode()
                )
                attempts = settings.provider_retries + 1
                cost = (
                    prompt_bound * settings.input_cost_per_million
                    + settings.max_output_tokens * settings.output_cost_per_million
                ) / 1e6
                budget.reserve(
                    (prompt_bound + settings.max_output_tokens) * attempts, cost * attempts
                )
            mark = perf_counter()
            with telemetry.stage("generation"):
                generation = await self.generator.generate(plan.rewritten, context)
            record("synthesize", f"Provider: {settings.generator}", mark)
            return generation

        generated = await generate(citations) if citations else Generation(answer=INSUFFICIENT)
        # Citation integrity remains mandatory even in a verification ablation.
        known_citations = {c.number for c in citations}
        referenced = {int(n) for n in re.findall(r"\[(\d+)\]", generated.answer)}
        if not referenced.issubset(known_citations):
            generated.answer = INSUFFICIENT
            warnings.append(
                "Generated answer contained invalid citation references and was withheld."
            )
        claims = []
        if request.verify:
            budget.step()
            mark = perf_counter()
            with telemetry.stage("verification"):
                claims = verify_claims(generated.answer, citations, settings.grounding_threshold)
            record(
                "verify",
                f"{sum(c.status == 'supported' for c in claims)}/{len(claims)} claims "
                "have exact source support.",
                mark,
            )
            bad = [c for c in claims if c.status != "supported"]
            if bad:
                telemetry.verification_failures.inc(len(bad))
                # One additional evidence lookup, followed by an exact-source correction.
                budget.step()
                mark = perf_counter()
                query = " ".join(c.text for c in bad)[:2000]
                result = await asyncio.to_thread(
                    self.engine.search,
                    snapshot,
                    query,
                    request.filters,
                    "hybrid_reranked",
                    request.top_k,
                )
                telemetry.tools.labels(tool="search_documents").inc()
                considered += result.considered
                warnings.extend(result.warnings)
                record(
                    "retrieve_again", "One verification-driven evidence lookup.", mark, result.hits
                )
                hits = reciprocal_rank_fusion([hits, result.hits], settings.rrf_k)
                citations = select_context(hits, settings.context_tokens, request.top_k)
                budget.step()
                mark = perf_counter()
                corrected = await ExtractiveGenerator().generate(plan.rewritten, citations)
                generated.answer = corrected.answer
                claims = verify_claims(generated.answer, citations, settings.grounding_threshold)
                warnings.append(
                    "Unverified generated claims were replaced with exact evidence excerpts."
                )
                record("correct_and_verify", "Applied conservative evidence-only correction.", mark)
        else:
            warnings.append("Verification disabled for this request; confidence is not assessed.")
        used = {int(n) for n in re.findall(r"\[(\d+)\]", generated.answer)}
        citations = [c for c in citations if c.number in used]
        if generated.answer == INSUFFICIENT:
            citations = []
        if settings.generator == "chat":
            warnings.append(
                "Cost uses returned provider usage; retry attempts reserve worst-case budget."
            )
        confidence = sum(c.status == "supported" for c in claims) / len(claims) if claims else 0
        budget.step()
        record("finish", "Returned answer, evidence and recorded actions.", perf_counter())
        return QueryResponse(
            answer=generated.answer,
            citations=citations,
            confidence=confidence,
            claims=claims,
            latency_ms=round((perf_counter() - started) * 1000, 3),
            trace=trace,
            generator=settings.generator,
            input_tokens=generated.input_tokens,
            output_tokens=generated.output_tokens,
            estimated_cost_usd=generated.estimated_cost_usd,
            warnings=list(dict.fromkeys(warnings)),
            retrieval=RetrievalInfo(
                strategy=request.strategy,
                chunks_considered=considered,
                chunks_used=len(citations),
                corpus_revision=snapshot.revision,
                queries=plan.queries,
                cache_hit=cache_hits == len(plan.queries),
                dense_backend=settings.dense_backend,
                reranker=settings.reranker,
            ),
        )

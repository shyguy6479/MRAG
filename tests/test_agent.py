from pathlib import Path

import httpx
import pytest

from atlasrag.agents.planning import plan_query
from atlasrag.agents.runner import Agent
from atlasrag.agents.tools import calculate
from atlasrag.core.cache import CacheStore
from atlasrag.core.config import Settings
from atlasrag.core.errors import BudgetExceeded, InvalidInput, ProviderUnavailable
from atlasrag.core.models import DocumentCreate, QueryRequest, SearchHit
from atlasrag.core.storage import Database
from atlasrag.generation.providers import INSUFFICIENT, ChatGenerator
from atlasrag.ingestion.service import IngestionService
from atlasrag.observability.telemetry import Telemetry
from atlasrag.retrieval.context import select_context
from atlasrag.retrieval.engine import RetrievalEngine
from atlasrag.verification.grounding import verify_claims
from tests.test_retrieval import evidence


def test_query_intelligence() -> None:
    assert plan_query("hello", []).intent == "conversation"
    assert plan_query("calculate (18 - 6) / 3", []).intent == "calculation"
    plan = plan_query("Compare quantization and speculative decoding", [])
    assert plan.intent == "comparison" and len(plan.queries) == 3
    assert (
        "quantization"
        in plan_query("What are its limitations?", ["Explain quantization"]).rewritten
    )
    assert (
        plan_query("What are its limitations?", ["Explain quantization"], False).rewritten
        == "What are its limitations?"
    )


@pytest.mark.parametrize(
    "expression", ["__import__('os')", "2**10000", "1/0", "True", "(1).__class__"]
)
def test_calculator_rejects_unsafe_inputs(expression: str) -> None:
    with pytest.raises(InvalidInput):
        calculate(expression)


def test_calculator_arithmetic() -> None:
    assert calculate("(120 - 30) / 3") == 30


def test_context_diversity_budget_duplicates_and_citations() -> None:
    text = "Quantization reduces memory requirements by storing weights at lower precision."
    hits = [
        SearchHit(evidence=evidence(1, text, 1), score=1),
        SearchHit(evidence=evidence(2, text, 1), score=0.9),
        SearchHit(
            evidence=evidence(
                3, "Speculative decoding uses a smaller draft model to propose output tokens.", 2
            ),
            score=0.8,
        ),
    ]
    citations = select_context(hits, 500, 3)
    assert len(citations) == 2
    assert len({c.document_id for c in citations}) == 2
    assert (
        sum(len(c.text.encode()) + len((c.title + c.section).encode()) + 32 for c in citations)
        <= 500
    )
    assert verify_claims(f'- "{text}" [1]', citations)[0].status == "supported"
    assert verify_claims("Costs decrease by 98 percent [1]", citations)[0].status == "unsupported"
    assert verify_claims("Quantization reduces memory [99]", citations)[0].status == "unsupported"


@pytest.mark.asyncio
async def test_agent_grounding_cache_and_deletion(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/test.db", environment="test", _env_file=None
    )
    db = Database(settings)
    db.initialize()
    telemetry = Telemetry()
    cache = CacheStore(settings, telemetry)
    ingestion = IngestionService(db, settings)
    doc = ingestion.submit(
        DocumentCreate(
            title="Quantization",
            content=(
                "Quantization reduces memory requirements by storing weights at lower precision. "
                "Aggressive quantization can reduce accuracy without calibration."
            ),
        )
    )
    ingestion.drain()
    engine = RetrievalEngine(db, settings, cache, telemetry)
    agent = Agent(engine, settings, telemetry)
    request = QueryRequest(question="How does quantization reduce memory?", decompose=False)
    answer = await agent.run(request)
    assert answer.citations and all(c.status == "supported" for c in answer.claims)
    assert all(c.document_id == doc.id for c in answer.citations)
    assert (await agent.run(request)).retrieval.cache_hit
    unrelated = await agent.run(QueryRequest(question="Who won the lunar football championship?"))
    assert unrelated.answer == INSUFFICIENT
    db.delete(doc.id)
    assert (await agent.run(request)).citations == []
    assert (await agent.run(QueryRequest(question="calculate 15/3"))).answer.endswith("= 5")
    tiny = Agent(engine, settings.model_copy(update={"max_agent_steps": 3}), telemetry)
    with pytest.raises(BudgetExceeded):
        await tiny.run(request)
    cache.close()
    db.close()
    telemetry.close()


@pytest.mark.asyncio
async def test_provider_failure_is_typed_and_sanitized() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(401, text="secret key bad"))
    generator = ChatGenerator(
        Settings(generator="chat", llm_model="test", llm_free_inference=True, _env_file=None),
        transport,
    )
    with pytest.raises(ProviderUnavailable) as caught:
        await generator.generate("question", [])
    assert "secret" not in caught.value.public_message

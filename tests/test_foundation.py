from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from atlasrag.api import create_app
from atlasrag.core.budget import Budget
from atlasrag.core.config import Settings
from atlasrag.core.errors import BudgetExceeded
from atlasrag.core.models import QueryRequest


def test_settings_validate_unsafe_combinations() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production", _env_file=None)
    with pytest.raises(ValidationError):
        Settings(chunk_size=30, chunk_overlap=30, _env_file=None)
    with pytest.raises(ValidationError):
        Settings(vector_backend="qdrant", dense_backend="lsa", _env_file=None)


def test_query_rejects_unknown_blank_and_invalid_ids() -> None:
    for data in [
        {"question": " "},
        {"question": "hello", "injected": True},
        {"question": "hello", "filters": {"document_ids": ["bad"]}},
    ]:
        with pytest.raises(ValidationError):
            QueryRequest.model_validate(data)
    assert QueryRequest(question="hello", filters={"document_ids": [uuid4()]}).top_k == 6


def test_budget_checks_before_side_effects() -> None:
    budget = Budget(max_steps=1, timeout_seconds=10, max_tokens=10, max_cost=0.01)
    assert budget.step() == 1
    with pytest.raises(BudgetExceeded):
        budget.step()
    budget.reserve(10, 0.01)
    with pytest.raises(BudgetExceeded):
        budget.reserve(1, 0)
    assert budget.tokens == 10


def test_api_health_security_and_metrics(tmp_path: Path) -> None:
    config = Settings(
        database_url=f"sqlite:///{tmp_path}/test.db",
        api_key="test-secret",
        environment="test",
        _env_file=None,
    )
    with TestClient(create_app(config)) as client:
        assert client.get("/health").json()["status"] == "ok"
        assert client.get("/ready").status_code == 200
        assert client.get("/openapi.json").status_code == 401
        response = client.get(
            "/openapi.json", headers={"x-api-key": "test-secret", "x-request-id": "test-123"}
        )
        assert response.status_code == 200
        assert response.headers["x-request-id"] == "test-123"
        assert int(response.headers["x-trace-id"], 16) > 0
        assert "rag_requests_total" in client.get("/metrics").text

import time
from pathlib import Path

from fastapi.testclient import TestClient

from atlasrag.api import create_app
from atlasrag.core.config import Settings


def test_scored_search_preserves_filters_without_generation(tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path}/search.db", environment="test")
    with TestClient(create_app(settings)) as client:
        doc = client.post(
            "/documents",
            json={"title": "Memory", "content": "Quantization reduces model memory usage."},
        ).json()
        for _ in range(50):
            if client.get(f"/documents/{doc['id']}").json()["document"]["status"] == "ready":
                break
            time.sleep(0.03)
        result = client.post(
            "/search", json={"question": "quantization memory", "strategy": "hybrid_reranked"}
        )
        assert result.status_code == 200
        payload = result.json()
        assert payload["hits"][0]["evidence"]["document_id"] == doc["id"]
        assert payload["hits"][0]["dense_score"] is not None
        assert payload["hits"][0]["sparse_score"] is not None
        assert payload["hits"][0]["rerank_score"] is not None
        assert "answer" not in payload
        assert client.get("/conversations").json() == []
        assert (
            client.post(
                "/search", json={"question": "memory", "filters": {"section": "missing"}}
            ).json()["hits"]
            == []
        )
        assert client.post("/search", json={"question": "memory", "top_k": 1000}).status_code == 422
        assert (
            client.post("/search", json={"question": "memory", "strategy": "agentic"}).status_code
            == 422
        )
        response = client.post(
            "/chat", json={"question": "How does quantization reduce memory?"}
        ).json()
        recent = client.get("/conversations").json()[0]
        assert recent["id"] == response["conversation_id"]
        assert recent["sources"] == 1
        assert recent["turns"] == 1
        assert recent["updated_at"].endswith("+00:00")
        assert recent["response"]["trace"] == response["trace"]


def test_workspace_adapters_auth_and_run_allowlist(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/auth.db",
        environment="test",
        api_key="workspace-test-key",
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/conversations").status_code == 401
        assert client.get("/evaluation-runs").status_code == 401
        assert client.post("/search", json={"question": "test"}).status_code == 401
        headers = {"X-API-Key": "workspace-test-key"}
        assert client.get("/evaluation-runs/not-a-run", headers=headers).status_code == 404
        runs = client.get("/evaluation-runs", headers=headers).json()
        assert {run["id"] for run in runs} == {"local", "neural"}
        run = client.get("/evaluation-runs/local", headers=headers).json()
        assert run["pipelines"][0]["name"] == "Dense (LSA)"
        assert len(run["questions"]) == 12

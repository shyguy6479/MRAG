from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from atlasrag.api import create_app
from atlasrag.core.config import Settings
from gateway.main import create_gateway


@pytest.fixture
def server_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MRAG_BACKEND_URL", "https://internal.example/")
    monkeypatch.setenv("ATLAS_API_KEY", "server-only-test-credential")


def test_gateway_supplies_server_key_and_does_not_forward_browser_credentials(
    server_env: None,
) -> None:
    seen = []

    def upstream(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"documents": 1}, headers={"X-API-Key": "never-forward"})

    with TestClient(create_gateway(httpx.MockTransport(upstream))) as client:
        assert client.get("/api/workspace").status_code == 200
        response = client.get(
            "/api/system?scope=current",
            headers={"X-API-Key": "browser-key", "Authorization": "Bearer browser-token"},
        )
        assert response.json() == {"documents": 1}
        assert response.headers["cache-control"] == "no-store"
        assert "x-api-key" not in response.headers
        assert "server-only" not in response.text
    assert str(seen[0].url) == "https://internal.example/api/system?scope=current"
    assert seen[0].headers["x-api-key"] == "server-only-test-credential"
    assert "authorization" not in seen[0].headers


def test_gateway_preserves_upload_bytes_and_rejects_foreign_browser_writes(
    server_env: None,
) -> None:
    seen = []

    def upstream(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(202, json={"status": "queued"})

    with TestClient(create_gateway(httpx.MockTransport(upstream))) as client:
        assert client.get("/api/workspace").status_code == 200
        rejected = client.post("/api/query", json={}, headers={"Origin": "https://evil.example"})
        assert rejected.status_code == 403 and not seen
        response = client.post(
            "/api/documents/upload", files={"file": ("test.pdf", b"%PDF-original-upload")}
        )
        assert response.status_code == 202
        assert b"%PDF-original-upload" in seen[0].content
        assert "multipart/form-data; boundary=" in seen[0].headers["content-type"]
        assert client.get("/api/docs").status_code == 404
        assert client.get("/api/openapi.json").status_code == 404
        assert client.get("/api/https://other.example/").status_code == 404


def test_gateway_fails_closed_without_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MRAG_BACKEND_URL", raising=False)
    monkeypatch.delenv("ATLAS_API_KEY", raising=False)
    monkeypatch.setenv("VERCEL", "1")
    with TestClient(create_gateway()) as client:
        assert client.get("/api/system").status_code == 503


def test_gateway_timeout_does_not_expose_provider_error(server_env: None) -> None:
    def upstream(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private-url-and-secret", request=request)

    with TestClient(create_gateway(httpx.MockTransport(upstream))) as client:
        client.get("/api/workspace")
        response = client.get("/api/system")
        assert response.status_code == 503 and "private-url-and-secret" not in response.text


def test_private_workspaces_isolate_documents_history_and_retrieval_cache(
    tmp_path: Path,
    server_env: None,
) -> None:
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path}/private.db",
        api_key="server-only-test-credential",
        _env_file=None,
    )
    backend = create_app(settings, api_prefix="/api")
    with TestClient(backend) as admin:
        assert admin.get("/api/documents").status_code == 401
        gateway = create_gateway(httpx.ASGITransport(app=backend))
        with TestClient(gateway) as first, TestClient(gateway) as second:
            assert first.get("/api/documents").status_code == 401
            first.get("/api/workspace")
            second.get("/api/workspace")
            assert first.cookies.get("mrag-workspace") != second.cookies.get("mrag-workspace")
            admitted = first.post(
                "/api/documents",
                json={
                    "title": "Private deployment",
                    "content": "MLOps skills include deployment and monitoring.",
                },
            )
            assert admitted.status_code == 202
            doc_id = admitted.json()["id"]
            backend.state.runtime.ingestion.drain()
            question = {"question": "Which MLOps skills include deployment and monitoring?"}
            owner_answer = first.post("/api/chat", json=question).json()
            assert owner_answer["citations"]
            assert first.post("/api/query", json=question).json()["retrieval"]["cache_hit"]
            assert first.get("/api/system").json()["chunks"] == 1
            assert second.get("/api/documents").json() == []
            assert second.get("/api/system").json()["chunks"] == 0
            assert second.get("/api/system").json()["jobs"] == {}
            assert second.get(f"/api/documents/{doc_id}").status_code == 404
            assert second.post(f"/api/documents/{doc_id}/retry").status_code == 404
            assert second.delete(f"/api/documents/{doc_id}").status_code == 404
            assert second.get("/api/conversations").json() == []
            assert second.get(f"/api/conversations/{owner_answer['conversation_id']}").json() == []
            answer = second.post("/api/query", json=question).json()
            assert answer["citations"] == []
            assert "MLOps skills include" not in answer["answer"]
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(
                    pool.map(
                        lambda pair: pair[0].get("/api/system").json()["chunks"],
                        [(first, 1), (second, 0)] * 5,
                    )
                )
            assert results == [1, 0] * 5
            assert first.get("/api/documents").json()[0]["id"] == doc_id
            assert first.post("/api/query", json=question).json()["citations"]
            # Supplying another tenant header cannot override the gateway's signed identity.
            foreign = second.get(
                "/api/documents",
                headers={"X-MRAG-Workspace": first.cookies.get("mrag-workspace").split(".")[0]},
            )
            assert foreign.json() == []
            # A forged cookie is rejected, never treated as an unrestricted backend request.
            second.cookies.set("mrag-workspace", "0" * 32 + ".invalid")
            assert second.get("/api/documents").status_code == 401
            # Another browser process with the valid cookie keeps its owner's private files.
            with TestClient(gateway, cookies=first.cookies) as reopened:
                assert reopened.get("/api/documents").json()[0]["id"] == doc_id

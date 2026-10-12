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
    with TestClient(create_gateway()) as client:
        assert client.get("/api/system").status_code == 503


def test_gateway_timeout_does_not_expose_provider_error(server_env: None) -> None:
    def upstream(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private-url-and-secret", request=request)

    with TestClient(create_gateway(httpx.MockTransport(upstream))) as client:
        response = client.get("/api/system")
        assert response.status_code == 503 and "private-url-and-secret" not in response.text


def test_two_anonymous_visitors_share_indexed_documents_and_research(
    tmp_path: Path, server_env: None
) -> None:
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path}/shared.db",
        api_key="server-only-test-credential",
        _env_file=None,
    )
    backend = create_app(settings, api_prefix="/api")
    with TestClient(backend) as admin:
        assert admin.get("/api/documents").status_code == 401
        gateway = create_gateway(httpx.ASGITransport(app=backend))
        with TestClient(gateway) as first:
            admitted = first.post(
                "/api/documents",
                json={
                    "title": "Shared skills",
                    "content": "MLOps skills include deployment and monitoring.",
                },
            )
            assert admitted.status_code == 202
            backend.state.runtime.ingestion.drain()
        with TestClient(gateway) as second:
            documents = second.get("/api/documents").json()
            assert documents[0]["id"] == admitted.json()["id"]
            assert documents[0]["chunk_count"] == 1
            answer = second.post(
                "/api/chat", json={"question": "Which MLOps skills include monitoring?"}
            )
            assert answer.status_code == 200 and answer.json()["citations"]
            assert second.get("/api/conversations").json()

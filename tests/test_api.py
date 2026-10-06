import time
from pathlib import Path

from fastapi.testclient import TestClient

from atlasrag.api import create_app
from atlasrag.core.config import Settings


def test_api_full_ingestion_research_chat_and_delete(tmp_path: Path) -> None:
    config = Settings(
        database_url=f"sqlite:///{tmp_path}/api.db", environment="test", _env_file=None
    )
    with TestClient(create_app(config)) as client:
        response = client.post(
            "/documents",
            json={
                "title": "Quantization",
                "content": (
                    "# Trade-offs\nQuantization reduces memory by storing weights "
                    "at lower precision. "
                    "Quantization can reduce accuracy when important outlier values "
                    "are poorly represented."
                ),
            },
        )
        assert response.status_code == 202
        doc_id = response.json()["id"]
        for _ in range(40):
            status = client.get(f"/documents/{doc_id}").json()["document"]["status"]
            if status == "ready":
                break
            time.sleep(0.05)
        assert status == "ready"
        result = client.post("/chat", json={"question": "How does quantization reduce memory?"})
        assert result.status_code == 200, result.text
        assert result.json()["citations"][0]["document_id"] == doc_id
        cid = result.json()["conversation_id"]
        followup = client.post(
            "/chat", json={"conversation_id": cid, "question": "What are its limitations?"}
        ).json()
        assert any(step["action"] == "rewrite" for step in followup["trace"])
        assert len(client.get(f"/conversations/{cid}").json()) == 2
        assert client.get("/system").json()["ready_documents"] == 1
        assert client.delete(f"/documents/{doc_id}").status_code == 204
        assert client.get(f"/documents/{doc_id}").status_code == 404
        assert client.post("/query", json={"question": "Quantization?"}).json()["citations"] == []


def test_upload_validation_limits_and_auth(tmp_path: Path) -> None:
    config = Settings(
        database_url=f"sqlite:///{tmp_path}/api.db",
        environment="test",
        max_upload_bytes=1024,
        rate_limit_per_minute=3,
        _env_file=None,
    )
    with TestClient(create_app(config)) as client:
        assert (
            client.post("/documents/upload", files={"file": ("evil.exe", b"bad")}).status_code
            == 400
        )
        assert (
            client.post("/documents/upload", files={"file": ("fake.pdf", b"bad")}).status_code
            == 400
        )
        assert client.post("/documents", content=b"x" * 70000).status_code == 413
        assert client.post("/query", json={"question": "hello"}).status_code == 429


def test_errors_do_not_leak_exception_messages(tmp_path: Path) -> None:
    config = Settings(
        database_url=f"sqlite:///{tmp_path}/api.db", environment="test", _env_file=None
    )
    app = create_app(config)

    @app.get("/test_failure")
    async def failure() -> None:
        raise RuntimeError("password=do-not-leak")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/test_failure")
        assert response.status_code == 500
        assert "do-not-leak" not in response.text
        assert response.json()["error"]["request_id"]

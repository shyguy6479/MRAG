from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from atlasrag.api import create_app
from atlasrag.core.config import Settings


def test_prefixed_api_auth_operations_and_openapi(tmp_path: Path) -> None:
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path}/deployment.db",
        api_key="test-workspace-key",
        allowed_origins=["https://mrag.example.com"],
        _env_file=None,
    )
    with TestClient(create_app(settings, api_prefix="/api")) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/ready").status_code == 200
        assert client.get("/api/metrics").status_code == 200
        assert client.get("/api/system").status_code == 401
        headers = {"X-API-Key": "test-workspace-key"}
        assert client.get("/api/system", headers=headers).status_code == 200
        assert client.get("/api/documents", headers=headers).json() == []
        cors = client.options(
            "/api/query",
            headers={
                "Origin": "https://mrag.example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "X-API-Key,Content-Type",
            },
        )
        assert cors.headers["access-control-allow-origin"] == "https://mrag.example.com"
        assert (
            client.post(
                "/api/query", json={"question": "What is retrieval?"}, headers=headers
            ).status_code
            == 200
        )
        metrics = client.get("/api/metrics").text
        assert 'route="/query"' in metrics
        assert 'route="/api/query"' not in metrics
        assert client.get("/api/docs", headers=headers).status_code == 200
        schema = client.get("/api/openapi.json", headers=headers).json()
        assert "/api/chat" in schema["paths"]
        assert "/api/documents/upload" in schema["paths"]
        assert client.get("/system", headers=headers).status_code == 404
        assert client.get("/api/unknown", headers=headers).status_code == 404


def test_vercel_entrypoint_import_without_local_env(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib
    import secrets
    import sys

    monkeypatch.setenv("ATLAS_DATABASE_URL", "postgresql+psycopg://user:placeholder@db.example/db")
    monkeypatch.setenv("ATLAS_REDIS_URL", "rediss://redis.example:6379/0")
    monkeypatch.setenv("ATLAS_API_KEY", secrets.token_hex(32))
    monkeypatch.delenv("ATLAS_ALLOWED_ORIGINS", raising=False)
    monkeypatch.setenv("ATLAS_MAX_UPLOAD_BYTES", "1048576")
    sys.modules.pop("app.main", None)
    entrypoint = importlib.import_module("app.main")
    assert entrypoint.app.openapi()["info"]["title"] == "MRAG"
    assert "/api/chat" in entrypoint.app.openapi()["paths"]
    settings = entrypoint.app.state.settings
    assert settings.environment == "production"
    assert settings.ingestion_mode == "celery"
    assert settings.allowed_origins == []
    assert settings.max_upload_bytes == 1048576
    entrypoint.app.state.telemetry.close()
    sys.modules.pop("app.main", None)

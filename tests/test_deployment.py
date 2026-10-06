import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from atlasrag.api import create_app
from atlasrag.core.config import Settings


def test_hosted_bundle_imports_without_installed_project(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    shutil.copytree(root / "app", tmp_path / "app", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(
        root / "src" / "atlasrag",
        tmp_path / "src" / "atlasrag",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    script = """
import importlib.util
import runpy
import sys
sys.path.insert(0, sys.argv[1])
assert importlib.util.find_spec('atlasrag') is None
module = runpy.run_path(sys.argv[2])
from fastapi.testclient import TestClient
with TestClient(module['app']) as client:
    response = client.get('/api/health')
    assert response.status_code == 503
    assert response.json()['error']['code'] == 'deployment_not_configured'
"""
    environment = {
        name: value for name, value in os.environ.items() if not name.startswith("ATLAS_")
    }
    subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-c",
            script,
            sysconfig.get_path("purelib"),
            str(tmp_path / "app" / "main.py"),
        ],
        cwd=tmp_path,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


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


def test_missing_vercel_configuration_returns_actionable_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib
    import sys

    for name in ("ATLAS_DATABASE_URL", "ATLAS_REDIS_URL", "ATLAS_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    sys.modules.pop("app.main", None)
    module = importlib.import_module("app.main")
    with TestClient(module.app) as client:
        for path in ("/api/health", "/api/system", "/api/ready"):
            response = client.get(path)
            assert response.status_code == 503
            body = response.json()
            assert body["error"]["code"] == "deployment_not_configured"
            assert set(body["missing_variables"]) == {
                "ATLAS_DATABASE_URL",
                "ATLAS_REDIS_URL",
                "ATLAS_API_KEY",
            }
            assert response.headers["cache-control"] == "no-store"
    sys.modules.pop("app.main", None)


def test_invalid_configuration_never_exposes_credential_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib
    import sys

    monkeypatch.setenv("ATLAS_DATABASE_URL", "postgresql+psycopg://user:private-password@db/db")
    monkeypatch.setenv("ATLAS_REDIS_URL", "rediss://user:private-redis-password@cache:6379/0")
    monkeypatch.setenv("ATLAS_API_KEY", "private-but-too-short-key")
    sys.modules.pop("app.main", None)
    module = importlib.import_module("app.main")
    with TestClient(module.app) as client:
        response = client.get("/api/system")
        assert response.status_code == 503
        assert "private-password" not in response.text
        assert "private-redis-password" not in response.text
        assert "private-but-too-short-key" not in response.text
    sys.modules.pop("app.main", None)


def test_failed_database_startup_returns_503_instead_of_crashing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from atlasrag.core.storage import Database

    def fail_initialize(self: Database) -> None:
        raise RuntimeError("private-database-password")

    monkeypatch.setattr(Database, "initialize", fail_initialize)
    settings = Settings(
        environment="test", database_url=f"sqlite:///{tmp_path}/failed.db", _env_file=None
    )
    with TestClient(
        create_app(settings, api_prefix="/api", tolerate_startup_failure=True)
    ) as client:
        for path in ("/api/health", "/api/system", "/api/ready"):
            response = client.get(path)
            assert response.status_code == 503
            assert response.json()["error"]["code"] == "storage_not_ready"
            assert "private-database-password" not in response.text
            assert "Alembic" in response.json()["error"]["message"]

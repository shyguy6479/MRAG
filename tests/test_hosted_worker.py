from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from atlasrag.api import create_app
from atlasrag.core.config import Settings
from atlasrag.core.storage import Database
from workers import vercel_tasks


@pytest.mark.parametrize("scheme", ["postgres", "postgresql", "postgresql+psycopg"])
def test_provider_postgres_url_uses_declared_driver(scheme: str) -> None:
    settings = Settings(database_url=f"{scheme}://user:placeholder@db.example/mrag?sslmode=require")
    assert (
        settings.database_url
        == "postgresql+psycopg://user:placeholder@db.example/mrag?sslmode=require"
    )


def test_queue_worker_indexes_committed_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from atlasrag.core import hosting

    settings = Settings(
        environment="test",
        ingestion_mode="vercel",
        database_url=f"sqlite:///{tmp_path}/hosted.db",
        api_key="test-workspace-key",
        _env_file=None,
    )
    notifications: list[None] = []
    monkeypatch.setattr(vercel_tasks.poll, "delay", lambda: notifications.append(None))
    monkeypatch.setattr(hosting, "deployment_settings", lambda: settings)
    with TestClient(create_app(settings)) as client:
        headers = {"X-API-Key": "test-workspace-key"}
        response = client.post(
            "/documents",
            json={
                "title": "Hosted evidence",
                "content": "MRAG keeps durable evidence in PostgreSQL.",
                "format": "txt",
            },
            headers=headers,
        )
        assert response.status_code == 202
        assert response.json()["status"] == "queued"
        assert len(notifications) == 1
        assert vercel_tasks.poll.run() is True
        assert len(notifications) == 2
        assert vercel_tasks.poll.run() is False
        document = client.get(f"/documents/{response.json()['id']}", headers=headers).json()
        assert document["document"]["status"] == "ready"
        assert len(document["chunks"]) > 0
        assert client.get("/ready").status_code == 200


def test_dispatch_failure_preserves_job_for_poll_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(
        environment="test",
        ingestion_mode="vercel",
        database_url=f"sqlite:///{tmp_path}/recover.db",
        _env_file=None,
    )

    def unavailable() -> None:
        raise RuntimeError("queue unavailable")

    monkeypatch.setattr(vercel_tasks.poll, "delay", unavailable)
    with TestClient(create_app(settings)) as client:
        result = client.post(
            "/documents",
            json={"title": "Recovery", "content": "Persistent document", "format": "txt"},
        )
        assert result.status_code == 202
        document_id = result.json()["id"]
        db = Database(settings)
        assert db.document(document_id)[0].status == "queued"
        db.close()
        notifications: list[None] = []
        monkeypatch.setattr(vercel_tasks.poll, "delay", lambda: notifications.append(None))
        assert client.get("/documents").json()[0]["status"] == "queued"
        assert len(notifications) == 1

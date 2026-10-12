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


def test_hosted_worker_schedules_durable_backoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import time

    from sqlalchemy import select

    from atlasrag.core import hosting
    from atlasrag.core.models import DocumentCreate
    from atlasrag.core.runtime import Runtime
    from atlasrag.core.storage import JobRow
    from atlasrag.observability.telemetry import Telemetry

    settings = Settings(
        environment="test",
        ingestion_mode="vercel",
        database_url=f"sqlite:///{tmp_path}/backoff.db",
        _env_file=None,
    )
    db = Database(settings)
    db.initialize()
    telemetry = Telemetry()
    runtime = Runtime(db, settings, telemetry)
    doc = runtime.ingestion.submit(DocumentCreate(title="Waiting", content="Stored for retry."))
    with db.sessions.begin() as session:
        job = session.scalar(select(JobRow).where(JobRow.document_id == str(doc.id)))
        job.lease_until = time.time() + 10
    delays = []
    monkeypatch.setattr(hosting, "deployment_settings", lambda: settings)
    monkeypatch.setattr(
        vercel_tasks.poll, "apply_async", lambda **kw: delays.append(kw["countdown"])
    )
    assert vercel_tasks.poll.run() is False
    assert len(delays) == 1 and 1 <= delays[0] <= 10
    runtime.close()
    telemetry.close()
    db.close()


def test_pdf_retrieval_after_worker_restart_has_page_citations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import io

    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    from atlasrag.core import hosting

    settings = Settings(
        environment="test",
        ingestion_mode="vercel",
        database_url=f"sqlite:///{tmp_path}/pdf.db",
        _env_file=None,
    )
    monkeypatch.setattr(hosting, "deployment_settings", lambda: settings)
    monkeypatch.setattr(vercel_tasks.poll, "delay", lambda: None)
    writer = PdfWriter()
    for text in (
        b"Machine learning and GenAI skills include Python, retrieval and model evaluation.",
        b"MLOps skills include deployment, monitoring and model versioning in production.",
    ):
        page = writer.add_blank_page(width=600, height=300)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        stream = DecodedStreamObject()
        stream.set_data(b"BT /F1 12 Tf 20 200 Td (" + text + b") Tj ET")
        page[NameObject("/Contents")] = stream
    raw = io.BytesIO()
    writer.write(raw)
    with TestClient(create_app(settings)) as client:
        response = client.post("/documents/upload", files={"file": ("skills.pdf", raw.getvalue())})
        assert response.status_code == 202
        doc_id = response.json()["id"]
    assert vercel_tasks.poll.run() is True
    # An independent API instance must rebuild retrieval from committed PostgreSQL-like rows.
    with TestClient(create_app(settings)) as client:
        detail = client.get(f"/documents/{doc_id}").json()
        assert detail["document"]["status"] == "ready"
        assert detail["document"]["chunk_count"] == 2
        for question, page in [
            ("Which GenAI skills include Python and evaluation?", 1),
            ("Which MLOps skills include deployment and monitoring?", 2),
        ]:
            answer = client.post("/query", json={"question": question}).json()
            assert answer["citations"]
            assert any(c["page"] == page for c in answer["citations"])
            assert "do not provide enough evidence" not in answer["answer"]
        assert client.post(f"/documents/{doc_id}/retry").status_code == 409


def test_manual_retry_endpoint_is_authenticated_and_keeps_original_upload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from atlasrag.core import hosting
    from atlasrag.core.storage import DocumentRow

    settings = Settings(
        environment="test",
        ingestion_mode="vercel",
        database_url=f"sqlite:///{tmp_path}/manual.db",
        api_key="workspace-test-key",
        _env_file=None,
    )
    monkeypatch.setattr(hosting, "deployment_settings", lambda: settings)
    monkeypatch.setattr(vercel_tasks.poll, "delay", lambda: None)
    headers = {"X-API-Key": "workspace-test-key"}
    raw = b"%PDF-a-corrupt-fixture"
    with TestClient(create_app(settings)) as client:
        admitted = client.post(
            "/documents/upload", headers=headers, files={"file": ("original.pdf", raw)}
        )
        doc_id = admitted.json()["id"]
        assert vercel_tasks.poll.run() is True
        assert (
            client.get(f"/documents/{doc_id}", headers=headers).json()["document"]["status"]
            == "failed"
        )
        assert client.post(f"/documents/{doc_id}/retry").status_code == 401
        retried = client.post(f"/documents/{doc_id}/retry", headers=headers)
        assert retried.status_code == 202
        assert retried.json()["id"] == doc_id
        assert retried.json()["status"] == "queued"
        db = Database(settings)
        with db.sessions() as session:
            assert session.get(DocumentRow, doc_id).raw == raw
        db.close()
        assert len(client.get("/documents", headers=headers).json()) == 1
        client.delete(f"/documents/{doc_id}", headers=headers)
        assert client.post(f"/documents/{doc_id}/retry", headers=headers).status_code == 404

from pathlib import Path

import pytest

from atlasrag.core.config import Settings
from atlasrag.core.errors import CapacityExceeded, InvalidInput, NotFound
from atlasrag.core.models import DocumentCreate
from atlasrag.core.storage import Database
from atlasrag.ingestion.chunking import chunk_sections
from atlasrag.ingestion.parsing import Section, parse
from atlasrag.ingestion.service import IngestionService


@pytest.fixture
def store(tmp_path: Path) -> Database:
    db = Database(
        Settings(database_url=f"sqlite:///{tmp_path}/ingest.db", environment="test", _env_file=None)
    )
    db.initialize()
    yield db
    db.close()


def test_html_strips_active_content() -> None:
    sections = parse(b"<h1>Results</h1><p>Latency improved.</p><script>steal()</script>", "html")
    assert sections[0].title == "Results"
    assert "steal" not in sections[0].text


def test_rejects_binary_pdf_and_empty_documents() -> None:
    for raw, format in [(b"MZbinary", "pdf"), (b"\x00abc", "txt"), (b"   ", "md")]:
        with pytest.raises(InvalidInput):
            parse(raw, format)


@pytest.mark.parametrize("strategy", ["fixed", "recursive", "semantic"])
def test_chunking_bounds_and_provenance(strategy: str) -> None:
    text = " ".join(f"word{i}" for i in range(110))
    chunks = chunk_sections([Section("Methods", text, 3)], strategy, 30, 5)
    assert chunks[-1].text.endswith("word109")
    assert all(len(c.text.split()) <= 30 and c.page == 3 for c in chunks)
    assert all(c.section == "Methods" for c in chunks)


def test_durable_job_index_and_delete(store: Database) -> None:
    service = IngestionService(store, store.settings)
    doc = service.submit(
        DocumentCreate(title="KV cache", content="# Method\nPaged blocks save memory.")
    )
    assert doc.status == "queued"
    assert store.snapshot()[1] == []
    # Reconstruct the service to model an API restart before the worker runs.
    assert IngestionService(store, store.settings).drain() == 1
    revision, evidence = store.snapshot()
    assert revision == 1 and len(evidence) == 1
    assert evidence[0].document_id == doc.id
    assert service.drain() == 0
    store.delete(doc.id)
    assert store.snapshot() == (2, [])
    with pytest.raises(NotFound):
        store.document(doc.id)


def test_index_failure_never_makes_document_visible(
    store: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(_: object) -> None:
        raise RuntimeError("provider secret must not be exposed")

    service = IngestionService(store, store.settings, index_writer=fail)
    doc = service.submit(DocumentCreate(title="Test", content="Some readable content."))
    clock = [1000.0]
    monkeypatch.setattr("atlasrag.ingestion.service.time.time", lambda: clock[0])
    for _ in range(3):
        assert service.process_one()
        assert store.snapshot()[1] == []
        clock[0] += 100
    assert store.document(doc.id)[0].status == "failed"
    assert "secret" not in str(store.document(doc.id)[0].error)
    assert store.snapshot()[1] == []


def test_upload_limit(store: Database) -> None:
    with pytest.raises(CapacityExceeded):
        IngestionService(store, store.settings).submit_bytes(
            "Huge", b"a" * (store.settings.max_upload_bytes + 1), "txt", "manual"
        )


def test_temporary_failure_backoff_and_manual_retry_reuses_raw(
    store: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy import select

    from atlasrag.core.storage import DocumentRow, JobRow

    clock = [1000.0]
    monkeypatch.setattr("atlasrag.ingestion.service.time.time", lambda: clock[0])

    def unavailable(_: object) -> None:
        raise ConnectionError("credential=do-not-expose")

    service = IngestionService(store, store.settings, index_writer=unavailable)
    doc = service.submit(DocumentCreate(title="Retry", content="MLOps requires model monitoring."))
    service.process_one()
    assert not service.process_one()  # Pending jobs cannot bypass their durable retry time.
    assert service.next_wakeup() == 5
    info, chunks = store.document(doc.id)
    assert info.status == "queued" and chunks == []
    assert "vector_index" in info.error and "ConnectionError" in info.error
    assert "credential" not in info.error
    service.index_writer = None
    clock[0] += 5
    assert service.process_one()
    assert store.document(doc.id)[0].status == "ready"
    assert service.next_wakeup() is None
    with store.sessions() as session:
        assert session.get(DocumentRow, str(doc.id)).raw
        assert session.scalar(select(JobRow).where(JobRow.document_id == str(doc.id))).attempts == 2


def test_manual_retry_failed_and_expired_lease_but_not_live_lease(store: Database) -> None:
    import time

    from sqlalchemy import select

    from atlasrag.core.errors import Conflict
    from atlasrag.core.storage import JobRow

    service = IngestionService(store, store.settings)
    doc = service.submit(DocumentCreate(title="Stored", content="GenAI needs evaluation."))
    with store.sessions.begin() as session:
        job = session.scalar(select(JobRow).where(JobRow.document_id == str(doc.id)))
        job.status, job.lease_until, job.lease_token = "running", time.time() + 180, "old"
    with pytest.raises(Conflict):
        service.retry(doc.id)
    with store.sessions.begin() as session:
        job = session.scalar(select(JobRow).where(JobRow.document_id == str(doc.id)))
        job.lease_until = 0
    assert service.retry(doc.id).status == "queued"
    service.process_one()
    assert store.document(doc.id)[0].chunk_count > 0
    with pytest.raises(Conflict):
        service.retry(doc.id)


def test_unreadable_pdf_error_identifies_extraction_stage(store: Database) -> None:
    service = IngestionService(store, store.settings)
    doc = service.submit_bytes("broken.pdf", b"%PDF-not-a-valid-document", "pdf", "manual")
    service.process_one()
    info, chunks = store.document(doc.id)
    assert info.status == "failed" and chunks == []
    assert "extraction: unreadable PDF" in info.error
    assert service.retry(doc.id).id == doc.id

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


def test_index_failure_never_makes_document_visible(store: Database) -> None:
    def fail(_: object) -> None:
        raise RuntimeError("provider secret must not be exposed")

    service = IngestionService(store, store.settings, index_writer=fail)
    doc = service.submit(DocumentCreate(title="Test", content="Some readable content."))
    assert service.drain() == 3
    assert store.document(doc.id)[0].status == "failed"
    assert "secret" not in str(store.document(doc.id)[0].error)
    assert store.snapshot()[1] == []


def test_upload_limit(store: Database) -> None:
    with pytest.raises(CapacityExceeded):
        IngestionService(store, store.settings).submit_bytes(
            "Huge", b"a" * (store.settings.max_upload_bytes + 1), "txt", "manual"
        )

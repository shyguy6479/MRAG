import hashlib
import logging
import time
from collections.abc import Callable
from uuid import UUID, uuid4, uuid5

from sqlalchemy import delete, func, or_, select, update

from atlasrag.core.config import Settings
from atlasrag.core.errors import CapacityExceeded, InvalidInput
from atlasrag.core.models import DocumentCreate, DocumentInfo, Evidence
from atlasrag.core.storage import ChunkRow, Database, DocumentRow, JobRow, RevisionRow
from atlasrag.ingestion.chunking import chunk_sections
from atlasrag.ingestion.parsing import parse

logger = logging.getLogger("atlasrag.ingestion")


class IngestionService:
    def __init__(
        self,
        db: Database,
        settings: Settings,
        index_writer: Callable[[list[Evidence]], None] | None = None,
    ) -> None:
        self.db, self.settings, self.index_writer = db, settings, index_writer

    def submit(self, data: DocumentCreate) -> DocumentInfo:
        return self.submit_bytes(
            data.title, data.content.encode(), data.format, data.source, data.chunking, data.tags
        )

    def submit_bytes(
        self,
        title: str,
        raw: bytes,
        format: str,
        source: str,
        chunking: str = "semantic",
        tags: list[str] | None = None,
    ) -> DocumentInfo:
        if not raw or not title.strip() or len(title) > 250 or len(source) > 1000:
            raise InvalidInput()
        if format not in {"pdf", "md", "html", "txt"}:
            raise InvalidInput("unsupported extension")
        if chunking not in {"fixed", "recursive", "semantic"}:
            raise InvalidInput("unknown chunk strategy")
        if len(raw) > self.settings.max_upload_bytes:
            raise CapacityExceeded()
        with self.db.lock, self.db.sessions.begin() as session:
            # Serialize admission against the corpus row on PostgreSQL as well as SQLite.
            session.execute(
                update(RevisionRow).where(RevisionRow.id == 1).values(value=RevisionRow.value)
            )
            count = (
                session.scalar(
                    select(func.count())
                    .select_from(DocumentRow)
                    .where(DocumentRow.status != "deleted")
                )
                or 0
            )
            if count >= self.settings.max_documents:
                raise CapacityExceeded()
            row = DocumentRow(
                id=str(uuid4()),
                title=title.strip(),
                raw=raw,
                format=format,
                source=source,
                chunking=chunking,
                tags=tags or [],
                status="queued",
                content_hash=hashlib.sha256(raw).hexdigest(),
            )
            session.add(row)
            session.flush()
            session.add(JobRow(id=str(uuid4()), document_id=row.id, status="queued"))
            return self.db.info(row)

    def process_one(self) -> bool:
        token, now = str(uuid4()), time.time()
        with self.db.sessions.begin() as session:
            # Use the same lock order as admission, deletion and index publication.
            session.execute(
                update(RevisionRow).where(RevisionRow.id == 1).values(value=RevisionRow.value)
            )
            eligible = or_(
                JobRow.status == "queued", (JobRow.status == "running") & (JobRow.lease_until < now)
            )
            job_id = session.scalar(select(JobRow.id).where(eligible).order_by(JobRow.id).limit(1))
            if job_id is None:
                return False
            claimed = session.execute(
                update(JobRow)
                .where(JobRow.id == job_id, eligible)
                .values(
                    status="running",
                    lease_until=now + 180,
                    lease_token=token,
                    attempts=JobRow.attempts + 1,
                )
            )
            if claimed.rowcount != 1:  # type: ignore[attr-defined]
                return False
            job = session.get(JobRow, job_id)
            assert job is not None
            doc = session.get(DocumentRow, job.document_id)
            assert doc is not None
            if doc.status == "deleted":
                job.status = "cancelled"
                return True
            if job.attempts > 3:
                job.status, doc.status, doc.error = (
                    "failed",
                    "failed",
                    "Worker retry limit reached.",
                )
                return True
            doc.status = "processing"
            doc_id, raw, format, strategy = doc.id, doc.raw, doc.format, doc.chunking
        try:
            sections = parse(raw, format)
            chunks = chunk_sections(
                sections, strategy, self.settings.chunk_size, self.settings.chunk_overlap
            )
            records = [
                ChunkRow(
                    id=str(uuid5(UUID(doc_id), f"{c.ordinal}:{c.text}")),
                    document_id=doc_id,
                    text=c.text,
                    section=c.section,
                    page=c.page,
                    ordinal=c.ordinal,
                )
                for c in chunks
            ]
            if len(records) > self.settings.max_chunks:
                raise CapacityExceeded()
            evidence = [self.db.evidence(doc, c) for c in records]
            if self.index_writer:
                self.index_writer(evidence)
            with self.db.sessions.begin() as session:
                session.execute(
                    update(RevisionRow).where(RevisionRow.id == 1).values(value=RevisionRow.value)
                )
                job = session.get(JobRow, job_id)
                doc = session.get(DocumentRow, doc_id)
                assert job is not None and doc is not None
                if job.lease_token != token or doc.status == "deleted":
                    return True
                total = (
                    session.scalar(
                        select(func.count())
                        .select_from(ChunkRow)
                        .where(ChunkRow.document_id != doc_id)
                    )
                    or 0
                )
                if total + len(records) > self.settings.max_chunks:
                    raise CapacityExceeded()
                session.execute(delete(ChunkRow).where(ChunkRow.document_id == doc_id))
                session.add_all(records)
                doc.status, doc.error = "ready", None
                job.status, job.lease_token = "complete", None
                self.db.bump(session)
        except Exception as exc:
            logger.warning("ingestion_failed", extra={"exception_type": type(exc).__name__})
            with self.db.sessions.begin() as session:
                job = session.get(JobRow, job_id)
                doc = session.get(DocumentRow, doc_id)
                if job and doc and job.lease_token == token and doc.status != "deleted":
                    permanent = isinstance(exc, (InvalidInput, CapacityExceeded))
                    retry = not permanent and job.attempts < 3
                    job.status = "queued" if retry else "failed"
                    doc.status = "queued" if retry else "failed"
                    doc.error = (
                        exc.public_message
                        if isinstance(exc, (InvalidInput, CapacityExceeded))
                        else "Indexing failed; inspect worker event logs."
                    )
        return True

    def drain(self) -> int:
        processed = 0
        while self.process_one():
            processed += 1
        return processed

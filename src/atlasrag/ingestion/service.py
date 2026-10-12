import hashlib
import logging
import math
import time
from collections.abc import Callable
from uuid import UUID, uuid4, uuid5

from sqlalchemy import delete, func, or_, select, update

from atlasrag.core.config import Settings
from atlasrag.core.errors import CapacityExceeded, Conflict, InvalidInput, NotFound
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
            result = self.db.info(row)
        logger.info("ingestion_admitted", extra={"document_id": str(result.id), "stage": "queued"})
        return result

    def retry(self, document_id: UUID) -> DocumentInfo:
        """Re-admit stored bytes without racing an active lease or re-uploading."""
        now = time.time()
        with self.db.lock, self.db.sessions.begin() as session:
            session.execute(
                update(RevisionRow).where(RevisionRow.id == 1).values(value=RevisionRow.value)
            )
            doc = session.get(DocumentRow, str(document_id))
            if doc is None or doc.status == "deleted":
                raise NotFound()
            job = session.scalar(select(JobRow).where(JobRow.document_id == doc.id))
            if doc.status == "ready":
                raise Conflict("This document is already indexed.")
            if job and job.status == "running" and job.lease_until > now:
                raise Conflict("This document is being processed. Retry after its lease expires.")
            if not job:
                job = JobRow(id=str(uuid4()), document_id=doc.id)
                session.add(job)
            job.status, job.attempts = "queued", 0
            job.lease_until, job.lease_token = 0, None
            doc.status, doc.error = "queued", None
            result = self.db.info(doc)
        logger.info("ingestion_retry_requested", extra={"document_id": str(document_id)})
        return result

    def next_wakeup(self) -> int | None:
        """Time until a durable retry or crashed worker lease becomes eligible."""
        with self.db.sessions() as session:
            due = session.scalar(
                select(func.min(JobRow.lease_until)).where(JobRow.status.in_(["queued", "running"]))
            )
        return None if due is None else max(1, math.ceil(due - time.time()))

    def process_one(self) -> bool:
        token, now = str(uuid4()), time.time()
        with self.db.sessions.begin() as session:
            # Use the same lock order as admission, deletion and index publication.
            session.execute(
                update(RevisionRow).where(RevisionRow.id == 1).values(value=RevisionRow.value)
            )
            eligible = or_(
                (JobRow.status == "queued") & (JobRow.lease_until <= now),
                (JobRow.status == "running") & (JobRow.lease_until < now),
            )
            job_id = session.scalar(select(JobRow.id).where(eligible).order_by(JobRow.id).limit(1))
            if job_id is None:
                return False
            claimed = session.execute(
                update(JobRow)
                .where(JobRow.id == job_id, eligible)
                .values(
                    status="running",
                    # Outlive the hosted function's 300s maximum to prevent overlapping
                    # processors after redelivery; Docker workers have a 120s limit.
                    lease_until=now + (360 if self.settings.ingestion_mode == "vercel" else 180),
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
            attempt = job.attempts
        started = time.monotonic()
        event = {"document_id": doc_id, "job_id": job_id, "attempt": attempt}
        stage = "extraction"
        logger.info("ingestion_started", extra={**event, "stage": stage})
        try:
            sections = parse(raw, format)
            logger.info("ingestion_extracted", extra={**event, "sections": len(sections)})
            stage = "chunking"
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
            if not records:
                raise InvalidInput("Document contains no indexable passages.")
            logger.info("ingestion_chunked", extra={**event, "chunks": len(records)})
            if len(records) > self.settings.max_chunks:
                raise CapacityExceeded()
            evidence = [self.db.evidence(doc, c) for c in records]
            stage = "vector_index"
            if self.index_writer:
                self.index_writer(evidence)
                logger.info("ingestion_vectors_stored", extra=event)
            stage = "publication"
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
                job.status, job.lease_token, job.lease_until = "complete", None, 0
                self.db.bump(session)
            logger.info(
                "ingestion_indexed",
                extra={
                    **event,
                    "chunks": len(records),
                    "sections": len(sections),
                    "duration_ms": round((time.monotonic() - started) * 1000),
                },
            )
        except Exception as exc:
            logger.warning(
                "ingestion_failed",
                extra={
                    **event,
                    "stage": stage,
                    "exception_type": type(exc).__name__,
                },
            )
            with self.db.sessions.begin() as session:
                job = session.get(JobRow, job_id)
                doc = session.get(DocumentRow, doc_id)
                if job and doc and job.lease_token == token and doc.status != "deleted":
                    permanent = isinstance(exc, (InvalidInput, CapacityExceeded))
                    retry = not permanent and job.attempts < 3
                    job.status = "queued" if retry else "failed"
                    doc.status = "queued" if retry else "failed"
                    job.lease_token = None
                    job.lease_until = (
                        time.time() + min(60, 5 * 2 ** (job.attempts - 1)) if retry else 0
                    )
                    # Parser/limit errors are controlled descriptions. Never expose arbitrary
                    # provider exception bodies, which may contain URLs or credentials.
                    reason = (
                        str(exc) or exc.public_message
                        if isinstance(exc, (InvalidInput, CapacityExceeded))
                        else f"{type(exc).__name__}; temporary provider or storage failure"
                    )
                    action = "Automatic retry scheduled." if retry else "Use Retry processing."
                    doc.error = f"{stage}: {reason}. {action}"[:250]
        return True

    def drain(self) -> int:
        processed = 0
        while self.process_one():
            processed += 1
        return processed

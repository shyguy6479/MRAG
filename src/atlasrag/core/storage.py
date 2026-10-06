import threading
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    LargeBinary,
    String,
    create_engine,
    event,
    func,
    select,
    text,
    update,
)
from sqlalchemy import delete as sql_delete
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from atlasrag.core.config import Settings
from atlasrag.core.errors import CapacityExceeded, NotFound
from atlasrag.core.models import DocumentInfo, DocumentStatus, Evidence, utcnow


class Base(DeclarativeBase):
    pass


class DocumentRow(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(250))
    source: Mapped[str] = mapped_column(String(1000))
    format: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), index=True)
    chunking: Mapped[str] = mapped_column(String(20))
    tags: Mapped[list[str]] = mapped_column(JSON)
    raw: Mapped[bytes] = mapped_column(LargeBinary)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    error: Mapped[str | None] = mapped_column(String(250), nullable=True)


class ChunkRow(Base):
    __tablename__ = "chunks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    text: Mapped[str]
    section: Mapped[str] = mapped_column(String(500))
    page: Mapped[int | None]
    ordinal: Mapped[int]


class JobRow(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), unique=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    lease_until: Mapped[float] = mapped_column(default=0)
    lease_token: Mapped[str | None] = mapped_column(String(36), nullable=True)


class RevisionRow(Base):
    __tablename__ = "corpus_revision"
    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[int] = mapped_column(default=0)


class MessageRow(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(36), index=True)
    question: Mapped[str]
    response: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Database:
    def __init__(self, settings: Settings) -> None:
        settings.prepare_sqlite_directory()
        args: dict[str, Any] = {"pool_pre_ping": True}
        if settings.database_url.startswith("sqlite"):
            args["connect_args"] = {"check_same_thread": False, "timeout": 15}
            if ":memory:" in settings.database_url:
                args["poolclass"] = StaticPool
        else:
            args["connect_args"] = {"connect_timeout": 3}
        self.engine = create_engine(settings.database_url, **args)
        if settings.database_url.startswith("sqlite"):

            @event.listens_for(self.engine, "connect")
            def configure_sqlite(connection: Any, _: Any) -> None:
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("PRAGMA journal_mode=WAL")

        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        self.settings = settings
        self.lock = threading.RLock()

    def initialize(self) -> None:
        # Production schema changes run through Alembic before API startup.
        if self.settings.environment != "production":
            Base.metadata.create_all(self.engine)
        with self.sessions.begin() as session:
            if session.get(RevisionRow, 1) is None:
                session.add(RevisionRow(id=1, value=0))

    def ping(self) -> bool:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True

    def revision(self) -> int:
        with self.sessions() as session:
            return int(session.scalar(select(RevisionRow.value).where(RevisionRow.id == 1)) or 0)

    @staticmethod
    def bump(session: Session) -> None:
        session.execute(
            update(RevisionRow).where(RevisionRow.id == 1).values(value=RevisionRow.value + 1)
        )

    def documents(self) -> list[DocumentInfo]:
        with self.sessions() as session:
            counts = dict(
                session.execute(
                    select(ChunkRow.document_id, func.count()).group_by(ChunkRow.document_id)
                ).all()
            )
            rows = session.scalars(
                select(DocumentRow)
                .where(DocumentRow.status != "deleted")
                .order_by(DocumentRow.created_at.desc())
            ).all()
            return [self.info(row, counts.get(row.id, 0)) for row in rows]

    @staticmethod
    def info(row: DocumentRow, count: int = 0) -> DocumentInfo:
        return DocumentInfo(
            id=UUID(row.id),
            title=row.title,
            source=row.source,
            format=row.format,
            status=DocumentStatus(row.status),
            chunking=row.chunking,
            tags=row.tags,
            created_at=row.created_at,
            chunk_count=count,
            error=row.error,
        )

    def document(self, document_id: UUID) -> tuple[DocumentInfo, list[Evidence]]:
        with self.sessions() as session:
            row = session.get(DocumentRow, str(document_id))
            if row is None or row.status == "deleted":
                raise NotFound()
            chunks = session.scalars(
                select(ChunkRow).where(ChunkRow.document_id == row.id).order_by(ChunkRow.ordinal)
            ).all()
            return self.info(row, len(chunks)), [self.evidence(row, c) for c in chunks]

    @staticmethod
    def evidence(doc: DocumentRow, chunk: ChunkRow) -> Evidence:
        return Evidence(
            chunk_id=UUID(chunk.id),
            document_id=UUID(doc.id),
            title=doc.title,
            source=doc.source,
            section=chunk.section,
            page=chunk.page,
            text=chunk.text,
            ordinal=chunk.ordinal,
            created_at=doc.created_at,
            tags=tuple(doc.tags),
        )

    def snapshot(self) -> tuple[int, list[Evidence]]:
        # Revision read before/after protects the READ COMMITTED PostgreSQL snapshot.
        for _ in range(4):
            before = self.revision()
            with self.sessions() as session:
                rows = session.execute(
                    select(DocumentRow, ChunkRow)
                    .join(ChunkRow, DocumentRow.id == ChunkRow.document_id)
                    .where(DocumentRow.status == "ready")
                    .order_by(ChunkRow.id)
                ).all()
                evidence = [self.evidence(doc, chunk) for doc, chunk in rows]
            if before == self.revision():
                return before, evidence
        raise CapacityExceeded("corpus changed too often; retry")

    def delete(self, document_id: UUID) -> None:
        with self.sessions.begin() as session:
            session.execute(
                update(RevisionRow).where(RevisionRow.id == 1).values(value=RevisionRow.value)
            )
            row = session.get(DocumentRow, str(document_id))
            if row is None or row.status == "deleted":
                raise NotFound()
            row.status = "deleted"
            row.raw = b""
            session.execute(sql_delete(ChunkRow).where(ChunkRow.document_id == row.id))
            session.execute(
                update(JobRow)
                .where(JobRow.document_id == row.id)
                .values(status="cancelled", lease_token=None)
            )
            self.bump(session)

    def close(self) -> None:
        self.engine.dispose()

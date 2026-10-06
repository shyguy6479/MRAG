import asyncio
import json
import logging
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select

from atlasrag.agents.tools import TOOL_SCHEMAS
from atlasrag.core.errors import CapacityExceeded, InvalidInput
from atlasrag.core.models import (
    ChatRequest,
    DocumentCreate,
    DocumentInfo,
    QueryRequest,
    QueryResponse,
)
from atlasrag.core.storage import JobRow, MessageRow

router = APIRouter()
logger = logging.getLogger("atlasrag.routes")


@router.get("/documents", response_model=list[DocumentInfo], tags=["documents"])
async def documents(request: Request) -> list[DocumentInfo]:
    return await asyncio.to_thread(request.app.state.db.documents)


@router.post("/documents", response_model=DocumentInfo, status_code=202, tags=["documents"])
async def create_document(data: DocumentCreate, request: Request) -> DocumentInfo:
    return await asyncio.to_thread(request.app.state.runtime.ingestion.submit, data)


@router.post("/documents/upload", response_model=DocumentInfo, status_code=202, tags=["documents"])
async def upload(
    request: Request, file: Annotated[UploadFile, File()], chunking: str = "semantic"
) -> DocumentInfo:
    name = Path(file.filename or "document.txt").name
    extension = Path(name).suffix.lower().lstrip(".")
    if extension not in {"pdf", "md", "txt", "html"}:
        raise InvalidInput("allowed: PDF, Markdown, text, HTML")
    settings = request.app.state.settings
    try:
        raw = await file.read(settings.max_upload_bytes + 1)
        if len(raw) > settings.max_upload_bytes:
            raise CapacityExceeded()
        if extension == "pdf" and not raw.startswith(b"%PDF-"):
            raise InvalidInput("invalid PDF signature")
        if extension != "pdf":
            try:
                raw.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise InvalidInput("invalid UTF-8") from exc
            if b"\x00" in raw:
                raise InvalidInput("binary upload rejected")
        return await asyncio.to_thread(
            request.app.state.runtime.ingestion.submit_bytes,
            name[:250],
            raw,
            extension,
            name,
            chunking,
        )
    finally:
        await file.close()


@router.get("/documents/{document_id}", tags=["documents"])
async def document(document_id: UUID, request: Request) -> dict[str, object]:
    info, chunks = await asyncio.to_thread(request.app.state.db.document, document_id)
    return {
        "document": info.model_dump(mode="json"),
        "chunks": [chunk.model_dump(mode="json") for chunk in chunks],
    }


@router.delete("/documents/{document_id}", status_code=204, tags=["documents"])
async def delete_document(document_id: UUID, request: Request) -> Response:
    await asyncio.to_thread(request.app.state.db.delete, document_id)
    qdrant = request.app.state.runtime.engine.qdrant
    if qdrant:
        try:
            await asyncio.to_thread(qdrant.delete_document, str(document_id))
        except Exception as exc:
            # The DB tombstone remains authoritative: stale vectors are excluded by ID filters.
            logger.warning("vector_cleanup_pending", extra={"exception_type": type(exc).__name__})
    return Response(status_code=204)


@router.post("/query", response_model=QueryResponse, tags=["research"])
async def query(data: QueryRequest, request: Request) -> QueryResponse:
    return await request.app.state.runtime.agent.run(data)


@router.post("/chat", response_model=QueryResponse, tags=["research"])
async def chat(data: ChatRequest, request: Request) -> QueryResponse:
    db = request.app.state.db
    conversation_id = data.conversation_id or uuid4()

    def memory() -> list[str]:
        with db.sessions() as session:
            return list(
                reversed(
                    session.scalars(
                        select(MessageRow.question)
                        .where(MessageRow.conversation_id == str(conversation_id))
                        .order_by(MessageRow.created_at.desc(), MessageRow.id.desc())
                        .limit(3)
                    ).all()
                )
            )

    result = await request.app.state.runtime.agent.run(data, await asyncio.to_thread(memory))
    result.conversation_id = conversation_id

    def save() -> None:
        with db.sessions.begin() as session:
            session.add(
                MessageRow(
                    id=str(result.id),
                    conversation_id=str(conversation_id),
                    question=data.question,
                    response=result.model_dump(mode="json"),
                )
            )

    await asyncio.to_thread(save)
    return result


@router.get("/conversations/{conversation_id}", tags=["research"])
async def conversation(conversation_id: UUID, request: Request) -> list[dict[str, Any]]:
    def read() -> list[dict[str, Any]]:
        with request.app.state.db.sessions() as session:
            rows = session.scalars(
                select(MessageRow)
                .where(MessageRow.conversation_id == str(conversation_id))
                .order_by(MessageRow.created_at.desc(), MessageRow.id.desc())
                .limit(100)
            ).all()
            return [{"question": row.question, "response": row.response} for row in reversed(rows)]

    return await asyncio.to_thread(read)


@router.get("/system", tags=["operations"])
async def system(request: Request) -> dict[str, object]:
    settings, runtime = request.app.state.settings, request.app.state.runtime
    db = request.app.state.db

    def stats() -> dict[str, object]:
        docs = db.documents()
        with db.sessions() as session:
            jobs = dict(
                session.execute(select(JobRow.status, func.count()).group_by(JobRow.status)).all()
            )
        return {
            "documents": len(docs),
            "ready_documents": sum(d.status == "ready" for d in docs),
            "chunks": sum(d.chunk_count for d in docs),
            "corpus_revision": db.revision(),
            "jobs": jobs,
        }

    return {
        **await asyncio.to_thread(stats),
        "profile": settings.environment,
        "dense_backend": settings.dense_backend,
        "vector_backend": settings.vector_backend,
        "reranker": settings.reranker,
        "generator": settings.generator,
        "embedding_model": settings.embedding_model
        if settings.dense_backend == "neural"
        else "TF-IDF + SVD",
        "cache_hits": runtime.cache.hits,
        "cache_misses": runtime.cache.misses,
        "max_agent_steps": settings.max_agent_steps,
        "query_timeout_seconds": settings.query_timeout_seconds,
        "context_budget_bytes": settings.context_tokens,
        "tool_schemas": [tool.model_dump() for tool in TOOL_SCHEMAS],
    }


@router.get("/evaluations", tags=["evaluation"])
async def evaluations() -> dict[str, object]:
    path = Path(__file__).resolve().parents[2] / "benchmarks" / "results" / "latest.json"
    # Packaged deployment path; benchmark artifacts are optional and never invented.
    if not path.exists():
        path = Path("benchmarks/results/latest.json")
    if not path.exists():
        return {
            "available": False,
            "message": "Run python scripts/benchmark.py to record measurements.",
        }
    return {"available": True, "results": json.loads(await asyncio.to_thread(path.read_text))}

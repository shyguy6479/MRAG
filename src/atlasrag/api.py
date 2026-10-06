import asyncio
import logging
import re
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.middleware.base import RequestResponseEndpoint

from atlasrag import __version__
from atlasrag.core.config import Settings
from atlasrag.core.errors import AtlasError
from atlasrag.core.limits import BodyLimitMiddleware, RateLimiter
from atlasrag.core.runtime import Runtime
from atlasrag.core.storage import Database
from atlasrag.observability.telemetry import Telemetry, configure_logging, request_id_var
from atlasrag.routes import router
from atlasrag.workspace_routes import router as workspace_router

logger = logging.getLogger("atlasrag.api")


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()
    telemetry = Telemetry(config.otlp_endpoint)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(config.log_level)
        app.state.db = Database(config)
        await asyncio.to_thread(app.state.db.initialize)
        app.state.runtime = await asyncio.to_thread(Runtime, app.state.db, config, telemetry)
        app.state.limiter = RateLimiter(app.state.runtime.cache, config.rate_limit_per_minute)
        stop = asyncio.Event()

        async def poll_jobs() -> None:
            while not stop.is_set():
                try:
                    await asyncio.to_thread(app.state.runtime.ingestion.process_one)
                except Exception as exc:
                    logger.error("job_poll_failed", extra={"exception_type": type(exc).__name__})
                try:
                    await asyncio.wait_for(stop.wait(), timeout=0.4)
                except TimeoutError:
                    pass

        worker = asyncio.create_task(poll_jobs()) if config.ingestion_mode == "local" else None
        try:
            yield
        finally:
            stop.set()
            if worker:
                await worker
            await asyncio.to_thread(app.state.runtime.close)
            await asyncio.to_thread(app.state.db.close)
            telemetry.close()

    app = FastAPI(
        title="MRAG",
        version=__version__,
        lifespan=lifespan,
        description="Inspectable retrieval, bounded tools, grounded research.",
    )
    app.state.settings = config
    app.state.telemetry = telemetry
    app.add_middleware(BodyLimitMiddleware, max_bytes=config.max_upload_bytes + 65536)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.allowed_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "X-API-Key", "X-Request-ID"],
        expose_headers=["X-Request-ID", "X-Trace-ID"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next: RequestResponseEndpoint) -> Response:
        rid = request.headers.get("x-request-id", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", rid):
            rid = str(uuid4())
        token = request_id_var.set(rid)
        request.state.request_id = rid
        started = perf_counter()
        status = 500
        response: Response
        try:
            with telemetry.tracer.start_as_current_span("http.request"):
                public = {"/health", "/ready", "/metrics"}
                key = config.api_key.get_secret_value()
                if key and request.url.path not in public and request.method != "OPTIONS":
                    if not secrets.compare_digest(request.headers.get("x-api-key", ""), key):
                        response = JSONResponse(
                            status_code=401,
                            content={
                                "error": {
                                    "code": "unauthorized",
                                    "message": "API key required.",
                                    "request_id": rid,
                                }
                            },
                        )
                        response.headers["X-Request-ID"] = rid
                        status = 401
                        return response
                if request.method in {"POST", "DELETE"}:
                    identity = key or (request.client.host if request.client else "local")
                    if not await asyncio.to_thread(app.state.limiter.allowed, identity):
                        response = JSONResponse(
                            status_code=429,
                            content={
                                "error": {
                                    "code": "rate_limited",
                                    "message": "Request limit reached.",
                                    "request_id": rid,
                                }
                            },
                            headers={"Retry-After": "60"},
                        )
                        response.headers["X-Request-ID"] = rid
                        status = 429
                        return response
                response = await call_next(request)
                status = response.status_code
                response.headers["X-Request-ID"] = rid
                response.headers["X-Trace-ID"] = telemetry.trace_id()
                return response
        except Exception as exc:
            status = exc.status_code if isinstance(exc, AtlasError) else 500
            logger.error("request_failed", extra={"exception_type": type(exc).__name__})
            return JSONResponse(
                status_code=status,
                headers={"X-Request-ID": rid},
                content={
                    "error": {
                        "code": exc.code if isinstance(exc, AtlasError) else "internal_error",
                        "message": exc.public_message
                        if isinstance(exc, AtlasError)
                        else "The request could not be completed.",
                        "request_id": rid,
                    }
                },
            )
        finally:
            route = getattr(request.scope.get("route"), "path", "unmatched")
            telemetry.requests.labels(route=route, status=str(status)).inc()
            telemetry.latency.labels(route=route).observe(perf_counter() - started)
            logger.info("request_completed")
            request_id_var.reset(token)

    @app.exception_handler(AtlasError)
    async def atlas_error(request: Request, exc: AtlasError) -> JSONResponse:
        logger.warning(exc.code, extra={"exception_type": type(exc).__name__})
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.public_message,
                    "request_id": request.state.request_id,
                }
            },
        )

    @app.get("/health", tags=["operations"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/ready", tags=["operations"])
    async def ready(request: Request) -> JSONResponse:
        try:
            await asyncio.wait_for(asyncio.to_thread(request.app.state.db.ping), timeout=4)
            cache = request.app.state.runtime.cache
            if cache.client:
                await asyncio.to_thread(cache.client.ping)
                if config.ingestion_mode == "celery":
                    heartbeat = await asyncio.to_thread(cache.client.get, "atlas:worker:heartbeat")
                    if not heartbeat:
                        return JSONResponse(
                            status_code=503, content={"status": "waiting_for_worker"}
                        )
            qdrant = request.app.state.runtime.engine.qdrant
            if qdrant:
                await asyncio.to_thread(qdrant.client.get_collections)
        except Exception as exc:
            logger.warning("readiness_failed", extra={"exception_type": type(exc).__name__})
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        return JSONResponse({"status": "ready"})

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(telemetry.registry), media_type=CONTENT_TYPE_LATEST)

    app.include_router(router)
    app.include_router(workspace_router)
    return app

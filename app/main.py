"""FastAPI entrypoint for Vercel Services."""

import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from atlasrag.api import create_app
from atlasrag.core.config import Settings


def deployment_settings() -> Settings:
    settings = Settings(environment="production", ingestion_mode="celery", _env_file=None)
    if "ATLAS_ALLOWED_ORIGINS" not in os.environ:
        settings.allowed_origins = []
    settings.max_upload_bytes = min(settings.max_upload_bytes, 3 * 1024 * 1024)
    return settings


def create_deployment_app() -> FastAPI:
    try:
        settings = deployment_settings()
    except ValidationError:
        # Never include ValidationError text: it can contain credential input values.
        required = ("ATLAS_DATABASE_URL", "ATLAS_REDIS_URL", "ATLAS_API_KEY")
        missing = [name for name in required if not os.environ.get(name)]
        names = ", ".join(missing) if missing else "the backend environment variables"
        message = (
            f"Deployment setup required: configure {names} in Vercel Production "
            "and redeploy. PostgreSQL, Redis and a workspace key of at least 32 "
            "characters are required. See the repository deployment guide."
        )
        diagnostic = FastAPI(title="MRAG", docs_url=None, redoc_url=None, openapi_url=None)

        @diagnostic.api_route(
            "/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
        )
        async def unavailable(path: str) -> JSONResponse:
            return JSONResponse(
                status_code=503,
                content={
                    "error": {"code": "deployment_not_configured", "message": message},
                    "status": "not_configured",
                    "missing_variables": missing,
                },
                headers={"Cache-Control": "no-store"},
            )

        return diagnostic
    return create_app(settings, api_prefix="/api", tolerate_startup_failure=True)


app = create_deployment_app()

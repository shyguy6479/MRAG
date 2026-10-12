"""FastAPI entrypoint for Vercel Services."""

import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from vercel.integrations.celery import install_vercel_celery_integration

# The runtime activates Celery before importing this entrypoint; retain its adapter.
install_vercel_celery_integration(register_queues=False)

# Vercel installs dependencies separately from the repository's src-layout package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from atlasrag.api import create_app  # noqa: E402
from atlasrag.core.hosting import deployment_settings  # noqa: E402


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

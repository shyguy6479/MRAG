"""FastAPI entrypoint for Vercel Services."""

import os

from atlasrag.api import create_app
from atlasrag.core.config import Settings


def deployment_settings() -> Settings:
    # Production must use durable external state and an external ingestion worker.
    settings = Settings(
        environment="production",
        ingestion_mode="celery",
        _env_file=None,
    )
    if "ATLAS_ALLOWED_ORIGINS" not in os.environ:
        settings.allowed_origins = []  # Same-origin /api requests need no CORS grant.
    settings.max_upload_bytes = min(settings.max_upload_bytes, 3 * 1024 * 1024)
    return settings


app = create_app(deployment_settings(), api_prefix="/api")

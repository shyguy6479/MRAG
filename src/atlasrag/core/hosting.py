"""Settings for hosted HTTP and queue functions."""

import os

from atlasrag.core.config import Settings


def deployment_settings() -> Settings:
    settings = Settings(environment="production", ingestion_mode="vercel", _env_file=None)  # type: ignore[call-arg]
    if "ATLAS_ALLOWED_ORIGINS" not in os.environ:
        settings.allowed_origins = []
    settings.max_upload_bytes = min(settings.max_upload_bytes, 3 * 1024 * 1024)
    return settings

import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict

import redis

from atlasrag.core.config import Settings
from atlasrag.observability.telemetry import Telemetry

logger = logging.getLogger("atlasrag.cache")


def cache_key(namespace: str, payload: object) -> str:
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return f"atlas:v1:{namespace}:{digest}"


class CacheStore:
    def __init__(self, settings: Settings, telemetry: Telemetry) -> None:
        self.settings, self.telemetry = settings, telemetry
        self.local: OrderedDict[str, tuple[float, str]] = OrderedDict()
        self.lock = threading.RLock()
        self.client = (
            redis.Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_timeout=2,
                socket_connect_timeout=2,
            )
            if settings.redis_url
            else None
        )
        self.hits, self.misses = 0, 0

    def get(self, key: str) -> str | None:
        value = None
        if self.client:
            try:
                value = self.client.get(key)
            except redis.RedisError as exc:
                logger.warning("cache_read_degraded", extra={"exception_type": type(exc).__name__})
        else:
            with self.lock:
                cached = self.local.get(key)
                if cached and cached[0] > time.monotonic():
                    value = cached[1]
                    self.local.move_to_end(key)
                elif cached:
                    del self.local[key]
        with self.lock:
            self.hits += value is not None
            self.misses += value is None
            self.telemetry.cache.labels(result="hit" if value is not None else "miss").inc()
            self.telemetry.cache_ratio.set(self.hits / (self.hits + self.misses))
        return str(value) if value is not None else None

    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        ttl = ttl_seconds or self.settings.cache_ttl_seconds
        if self.client:
            try:
                self.client.setex(key, ttl, value)
            except redis.RedisError as exc:
                logger.warning("cache_write_degraded", extra={"exception_type": type(exc).__name__})
            return
        with self.lock:
            self.local[key] = (time.monotonic() + ttl, value)
            self.local.move_to_end(key)
            while len(self.local) > self.settings.cache_max_entries:
                self.local.popitem(last=False)

    def close(self) -> None:
        if self.client:
            self.client.close()

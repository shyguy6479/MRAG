import hashlib
import threading
import time
from collections import OrderedDict
from typing import Any, cast

from atlasrag.core.cache import CacheStore
from atlasrag.core.errors import ProviderUnavailable


class RateLimiter:
    def __init__(self, cache: CacheStore, limit: int) -> None:
        self.cache, self.limit = cache, limit
        self.counts: OrderedDict[str, tuple[int, int]] = OrderedDict()
        self.lock = threading.RLock()

    def allowed(self, identity: str) -> bool:
        window = int(time.time() // 60)
        key = "atlas:rate:" + hashlib.sha256(identity.encode()).hexdigest() + f":{window}"
        if self.cache.client:
            try:
                redis_count = self.cache.client.eval(
                    "local n=redis.call('INCR',KEYS[1]); "
                    "if n==1 then redis.call('EXPIRE',KEYS[1],120) end; return n",
                    1,
                    key,
                )
                return int(cast(str, redis_count)) <= self.limit
            except Exception as exc:
                # A shared limiter must fail closed, never silently become per-process.
                raise ProviderUnavailable("rate limiter unavailable") from exc
        with self.lock:
            current, count = self.counts.get(identity, (window, 0))
            count = count + 1 if current == window else 1
            self.counts[identity] = (window, count)
            self.counts.move_to_end(identity)
            while len(self.counts) > 4096:
                self.counts.popitem(last=False)
            return count <= self.limit


class BodyLimitMiddleware:
    """Bound bytes before JSON parsing or multipart spooling, including chunked bodies."""

    def __init__(self, app: Any, max_bytes: int) -> None:
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            await self.app(scope, receive, send)
            return
        from starlette.responses import JSONResponse

        size = 0
        chunks = []
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.max_bytes:
                response = JSONResponse(
                    {
                        "error": {
                            "code": "upload_too_large",
                            "message": "Request body exceeds the configured limit.",
                        }
                    },
                    status_code=413,
                )
                await response(scope, receive, send)
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay() -> Any:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)

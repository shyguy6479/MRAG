"""Public shared-workspace gateway. Backend credentials never reach the browser."""

import logging
import os
import re
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

logger = logging.getLogger("mrag.gateway")
UUID = r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}"
ROUTES = {
    "GET": re.compile(
        rf"(?:health|ready|metrics|system|documents(?:/{UUID})?|"
        rf"conversations(?:/{UUID})?|evaluations|evaluation-runs(?:/(?:local|neural))?)"
    ),
    "POST": re.compile(rf"(?:query|chat|search|documents(?:/upload|/{UUID}/retry)?)"),
    "DELETE": re.compile(rf"documents/{UUID}"),
}
MAX_BODY = 5 * 1024 * 1024


def create_gateway(transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    gateway = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @gateway.api_route("/api/{path:path}", methods=["GET", "POST", "DELETE", "PUT", "PATCH"])
    async def proxy(path: str, request: Request) -> Response:
        pattern = ROUTES.get(request.method)
        if pattern is None or pattern.fullmatch(path) is None:
            return JSONResponse({"error": {"message": "Route not available."}}, status_code=404)
        # The workspace is public, but another website must not perform browser writes.
        origin = request.headers.get("origin")
        if request.method != "GET" and (
            request.headers.get("sec-fetch-site") == "cross-site"
            or (origin and urlsplit(origin).netloc != request.url.netloc)
        ):
            return JSONResponse({"error": {"message": "Request not allowed."}}, status_code=403)
        base = os.environ.get("MRAG_BACKEND_URL", "")
        key = os.environ.get("ATLAS_API_KEY", "")
        if not base or not key:
            return JSONResponse(
                {
                    "error": {
                        "message": "Workspace temporarily unavailable. Please try again later."
                    }
                },
                status_code=503,
                headers={"Cache-Control": "no-store"},
            )
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_BODY:
                return JSONResponse(
                    {"error": {"message": "Upload exceeds the 5 MB request limit."}},
                    status_code=413,
                )
        # Fixed allowlisted paths and a trusted binding prevent an arbitrary proxy/SSRF.
        target = base.rstrip("/") + "/api/" + path
        if request.url.query:
            target += "?" + request.url.query
        headers = {"X-API-Key": key}
        for name in ("content-type", "accept", "x-request-id"):
            if value := request.headers.get(name):
                headers[name] = value
        try:
            async with httpx.AsyncClient(
                transport=transport, timeout=55, follow_redirects=False
            ) as client:
                upstream = await client.request(
                    request.method, target, content=bytes(body), headers=headers
                )
        except httpx.HTTPError as exc:
            logger.warning("backend_unavailable", extra={"exception_type": type(exc).__name__})
            return JSONResponse(
                {"error": {"message": "Workspace temporarily unavailable. Please try again."}},
                status_code=503,
                headers={"Cache-Control": "no-store"},
            )
        if 300 <= upstream.status_code < 400:
            return JSONResponse(
                {"error": {"message": "Workspace temporarily unavailable."}}, status_code=502
            )
        response_headers = {"Cache-Control": "no-store"}
        for name in ("content-type", "x-request-id", "x-trace-id", "retry-after"):
            if value := upstream.headers.get(name):
                response_headers[name] = value
        return Response(
            upstream.content, status_code=upstream.status_code, headers=response_headers
        )

    return gateway


app = create_gateway()

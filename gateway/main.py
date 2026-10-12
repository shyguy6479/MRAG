"""Private browser-workspace gateway. Backend credentials never reach the browser."""

import hashlib
import hmac
import logging
import os
import re
from urllib.parse import urlsplit
from uuid import uuid4

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
COOKIE = "mrag-workspace"


def read_workspace(value: str, key: str) -> str | None:
    tenant, _, signature = value.partition(".")
    expected = hmac.new(key.encode(), tenant.encode(), hashlib.sha256).hexdigest()
    return (
        tenant
        if re.fullmatch(r"[0-9a-f]{32}", tenant) and hmac.compare_digest(signature, expected)
        else None
    )


def create_gateway(transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    gateway = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @gateway.api_route("/api/{path:path}", methods=["GET", "POST", "DELETE", "PUT", "PATCH"])
    async def proxy(path: str, request: Request) -> Response:
        origin = request.headers.get("origin")
        if (request.method != "GET" or path == "workspace") and (
            request.headers.get("sec-fetch-site") == "cross-site"
            or (origin and urlsplit(origin).netloc != request.url.netloc)
        ):
            return JSONResponse({"error": {"message": "Request not allowed."}}, status_code=403)
        base = os.environ.get("MRAG_BACKEND_URL", "")
        key = os.environ.get("ATLAS_API_KEY", "")
        local = not os.environ.get("VERCEL") and not base
        if local:
            base, key = "http://127.0.0.1:8000", key or "local-workspace"
        if not base or not key:
            return JSONResponse(
                {"error": {"message": "Workspace temporarily unavailable."}}, status_code=503
            )
        tenant = read_workspace(request.cookies.get(COOKIE, ""), key)
        if path == "workspace" and request.method == "GET":
            tenant = tenant or uuid4().hex
            signature = hmac.new(key.encode(), tenant.encode(), hashlib.sha256).hexdigest()
            response = JSONResponse(
                {"private": True, "workspace_id": tenant}, headers={"Cache-Control": "no-store"}
            )
            response.set_cookie(
                COOKIE,
                f"{tenant}.{signature}",
                max_age=31536000,
                httponly=True,
                secure=bool(os.environ.get("VERCEL")) or request.url.scheme == "https",
                samesite="strict",
                path="/",
            )
            return response
        if tenant is None:
            return JSONResponse(
                {"error": {"message": "Open your workspace and try again."}}, status_code=401
            )
        pattern = ROUTES.get(request.method)
        if pattern is None or pattern.fullmatch(path) is None:
            return JSONResponse({"error": {"message": "Route not available."}}, status_code=404)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_BODY:
                return JSONResponse(
                    {"error": {"message": "Upload exceeds the 5 MB request limit."}},
                    status_code=413,
                )
        # Fixed allowlisted paths and a trusted binding prevent an arbitrary proxy/SSRF.
        prefix = os.environ.get("MRAG_BACKEND_API_PREFIX", "" if local else "/api")
        target = base.rstrip("/") + prefix.rstrip("/") + "/" + path
        if request.url.query:
            target += "?" + request.url.query
        headers = {"X-API-Key": key, "X-MRAG-Workspace": tenant}
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

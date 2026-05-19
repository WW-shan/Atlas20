"""Request ID middleware."""

from __future__ import annotations

import re
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _request_id_from_header(header_value: str | None) -> str:
    if header_value is not None:
        request_id = header_value.strip()
        if REQUEST_ID_RE.fullmatch(request_id):
            return request_id
    return uuid.uuid4().hex


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = _request_id_from_header(request.headers.get("X-Request-ID"))
        request.state.request_id = request_id
        tokens = structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.reset_contextvars(**tokens)
        response.headers["X-Request-ID"] = request_id
        return response

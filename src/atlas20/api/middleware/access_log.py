"""HTTP access logging middleware."""

from __future__ import annotations

import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


logger = structlog.get_logger("atlas20.api.access")


class AccessLogMiddleware(BaseHTTPMiddleware):
    excluded_paths = {"/healthz", "/readyz", "/metrics"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter_ns()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            path = request.url.path
            if path not in self.excluded_paths:
                duration_ms = round((time.perf_counter_ns() - start) / 1_000_000, 3)
                client_ip = request.client.host if request.client else None
                request_id = getattr(request.state, "request_id", None)
                logger.info(
                    "request",
                    method=request.method,
                    path=path,
                    status=status_code,
                    duration_ms=duration_ms,
                    request_id=request_id,
                    client_ip=client_ip,
                )

"""Prometheus instrumentation setup."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import time

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest


EXCLUDED_PATHS = {"/healthz", "/readyz", "/metrics"}
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests.",
    ["handler", "method", "status"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["handler", "method"],
)


def _handler_for_request(request: Request) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    return str(route_path) if route_path else request.url.path


def instrument_metrics(app: FastAPI) -> None:
    if getattr(app.state, "metrics_instrumented", False):
        return

    @app.middleware("http")
    async def metrics_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path in EXCLUDED_PATHS:
            return await call_next(request)

        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            handler = _handler_for_request(request)
            HTTP_REQUESTS_TOTAL.labels(
                handler=handler,
                method=request.method,
                status=f"{status_code // 100}xx",
            ).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(handler=handler, method=request.method).observe(
                max(0.0, time.perf_counter() - started)
            )

    app.state.metrics_instrumented = True


def expose_metrics(app: FastAPI) -> None:
    if getattr(app.state, "metrics_exposed", False):
        return

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    app.state.metrics_exposed = True

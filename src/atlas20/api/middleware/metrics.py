"""Prometheus instrumentation setup."""

from __future__ import annotations

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator


def instrument_metrics(app: FastAPI) -> None:
    if getattr(app.state, "metrics_instrumented", False):
        return
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=["^/healthz$", "^/readyz$"],
    ).instrument(app)
    app.state.metrics_instrumentator = instrumentator
    app.state.metrics_instrumented = True


def expose_metrics(app: FastAPI) -> None:
    if getattr(app.state, "metrics_exposed", False):
        return
    instrumentator = getattr(app.state, "metrics_instrumentator", None)
    if instrumentator is None:
        instrument_metrics(app)
        instrumentator = app.state.metrics_instrumentator
    instrumentator.expose(app, endpoint="/metrics", include_in_schema=False)
    app.state.metrics_exposed = True

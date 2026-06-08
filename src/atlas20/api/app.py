"""FastAPI application factory for the Atlas20 research console."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
from typing import Any, cast

from atlas20._version import __version__
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from atlas20.api._log_redact import scrub_sensitive_headers as _scrub_sensitive_headers
from atlas20.api.dependencies.ratelimit import limiter, rate_limit_exceeded_handler, reset_rate_limit_storage
from atlas20.api.db.migrate import upgrade_to_head
from atlas20.api.errors import http_exception_handler, unhandled_exception_handler, validation_exception_handler
from atlas20.api.logging_config import configure_logging
from atlas20.api.middleware.access_log import AccessLogMiddleware
from atlas20.api.middleware.metrics import expose_metrics, instrument_metrics
from atlas20.api.middleware.request_id import RequestIdMiddleware
from atlas20.api.routes.backtests import router as backtests_router
from atlas20.api.routes.compare import router as compare_router
from atlas20.api.routes.health import router as health_router
from atlas20.api.routes.options import router as options_router
from atlas20.api.routes.overview import router as overview_router
from atlas20.api.routes.reports import router as reports_router
from atlas20.api.routes.runs import router as runs_router
from atlas20.api.routes.universe import router as universe_router
from atlas20.api.scheduler import start_scheduler
from atlas20.api.settings import Settings, get_settings
from atlas20.api.worker.main import session_scope
from atlas20.api.worker.recovery import recover_stale_runs

logger = logging.getLogger(__name__)


def _init_sentry(settings: Settings) -> None:
    if not settings.sentry_dsn:
        return
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.env,
        traces_sample_rate=0.0,
        send_default_pii=False,
        before_send=cast(Any, _scrub_sensitive_headers),
        integrations=[FastApiIntegration()],
    )


def _warn_if_shadow_install() -> None:
    """Warn when an installed copy of `atlas20` shadows the repo `src/` tree.

    Thin compatibility shim; the real implementation lives in
    `atlas20.api.install_check` so the worker can call it without importing
    this whole module's FastAPI / middleware / routes tree.
    """
    from atlas20.api.install_check import warn_if_shadow_install

    warn_if_shadow_install()


def _include_health_routes(app: FastAPI) -> None:
    if getattr(app.state, "health_routes_included", False):
        return
    app.include_router(health_router)
    app.state.health_routes_included = True


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    _warn_if_shadow_install()
    _init_sentry(settings)
    _include_health_routes(app)
    expose_metrics(app)
    upgrade_to_head(settings)
    try:
        with session_scope(settings) as session:
            recovered = recover_stale_runs(session, stale_after_seconds=60)
    except ModuleNotFoundError:
        if settings.db_url.startswith("sqlite"):
            raise
        logger.warning("Skipping stale run recovery because the DB driver is unavailable")
        recovered = 0
    if recovered:
        logger.info("Recovered %d stale running runs", recovered)
    scheduler = start_scheduler(settings)
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)
    docs_url = "/docs" if settings.enable_docs else None
    redoc_url = "/redoc" if settings.enable_docs else None
    openapi_url = "/openapi.json" if settings.enable_docs else None
    app = FastAPI(
        title="Atlas20 Research Console API",
        version=__version__,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )
    app.state.limiter = limiter
    reset_rate_limit_storage()
    app.add_exception_handler(StarletteHTTPException, cast(Any, http_exception_handler))
    app.add_exception_handler(RequestValidationError, cast(Any, validation_exception_handler))
    app.add_exception_handler(RateLimitExceeded, cast(Any, rate_limit_exceeded_handler))
    app.add_exception_handler(Exception, cast(Any, unhandled_exception_handler))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # reports/ filesystem access stays behind API routes; do not mount StaticFiles here.
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.include_router(overview_router)
    app.include_router(options_router)
    app.include_router(runs_router)
    app.include_router(backtests_router)
    app.include_router(compare_router)
    app.include_router(universe_router)
    app.include_router(reports_router)
    instrument_metrics(app)
    return app


app = create_app()

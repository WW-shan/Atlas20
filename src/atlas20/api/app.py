"""FastAPI application factory for the Atlas20 research console."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from filelock import FileLock
from sqlalchemy.engine import make_url

from atlas20.api.logging_config import configure_logging
from atlas20.api.middleware.access_log import AccessLogMiddleware
from atlas20.api.middleware.request_id import RequestIdMiddleware
from atlas20.api.routes.backtests import router as backtests_router
from atlas20.api.routes.compare import router as compare_router
from atlas20.api.routes.options import router as options_router
from atlas20.api.routes.overview import router as overview_router
from atlas20.api.routes.reports import router as reports_router
from atlas20.api.routes.runs import router as runs_router
from atlas20.api.routes.universe import router as universe_router
from atlas20.api.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    from alembic.config import Config
    from alembic import command

    settings = get_settings()
    url = make_url(settings.db_url)
    if url.drivername.startswith("sqlite") and url.database:
        db_path = Path(url.database)
        lock_path = db_path.with_suffix(".alembic.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(str(lock_path), timeout=60):
            cfg = Config("alembic.ini")
            command.upgrade(cfg, "head")
    else:
        # Postgres/MySQL: rely on alembic_version table + advisory locks (Batch 14 follow-up)
        cfg = Config("alembic.ini")
        command.upgrade(cfg, "head")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)
    docs_url = "/docs" if settings.enable_docs else None
    redoc_url = "/redoc" if settings.enable_docs else None
    openapi_url = "/openapi.json" if settings.enable_docs else None
    app = FastAPI(
        title="Atlas20 Research Console API",
        version="0.1.0",
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.include_router(overview_router)
    app.include_router(options_router)
    app.include_router(runs_router)
    app.include_router(backtests_router)
    app.include_router(compare_router)
    app.include_router(universe_router)
    app.include_router(reports_router)
    return app


app = create_app()

"""FastAPI application factory for the Atlas20 research console."""

from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from filelock import FileLock
from slowapi.errors import RateLimitExceeded
from sqlalchemy.engine import make_url

from atlas20.api._log_redact import scrub_sensitive_headers as _scrub_sensitive_headers
from atlas20.api.dependencies.ratelimit import limiter, rate_limit_exceeded_handler, reset_rate_limit_storage
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
from atlas20.api.settings import get_settings
from atlas20.api.worker.main import session_scope
from atlas20.api.worker.recovery import recover_stale_runs

logger = logging.getLogger(__name__)


def _alembic_config(settings):
    from alembic.config import Config

    cwd_config = Path("alembic.ini")
    root_config = Path(settings.project_root) / "alembic.ini"
    config_path = cwd_config if cwd_config.exists() else root_config
    cfg = Config(str(config_path))
    script_location = cfg.get_main_option("script_location") if hasattr(cfg, "get_main_option") else None
    if script_location and ":" not in script_location and hasattr(cfg, "set_main_option"):
        script_path = Path(script_location)
        if not script_path.is_absolute():
            cfg.set_main_option("script_location", str((config_path.parent / script_path).resolve()))
    return cfg


def _init_sentry(settings) -> None:
    if not settings.sentry_dsn:
        return
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.env,
        traces_sample_rate=0.0,
        send_default_pii=False,
        before_send=_scrub_sensitive_headers,
        integrations=[FastApiIntegration()],
    )


def _warn_if_shadow_install() -> None:
    """Warn when an installed copy of `atlas20` shadows the repo `src/` tree.

    A non-editable `pip install .` plants the package in site-packages, which
    sys.path resolves before the repo's `src/` layout. Edits to `src/` then
    have no runtime effect, while pytest still passes because pyproject sets
    `pythonpath=["src"]`. This is silent in Docker (the image has no
    `src/atlas20/__init__.py` at `/app`) and silent under PYTHONPATH=src or
    editable installs (atlas20.__file__ already lives under the repo).
    """
    import atlas20

    repo_init = Path.cwd() / "src" / "atlas20" / "__init__.py"
    if not repo_init.exists():
        return
    loaded_from = Path(atlas20.__file__).resolve()
    expected_under = repo_init.parent.resolve()
    try:
        loaded_from.relative_to(expected_under)
    except ValueError:
        logger.warning(
            "atlas20 was imported from %s but the repo has src/atlas20/ at %s; "
            "runtime is using a stale installed copy. Run "
            "`python -m pip install -e .` or set PYTHONPATH=src so edits take effect.",
            loaded_from,
            expected_under,
        )


def _include_health_routes(app: FastAPI) -> None:
    if getattr(app.state, "health_routes_included", False):
        return
    app.include_router(health_router)
    app.state.health_routes_included = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    from alembic import command

    settings = get_settings()
    _warn_if_shadow_install()
    _init_sentry(settings)
    _include_health_routes(app)
    expose_metrics(app)
    url = make_url(settings.db_url)
    if url.drivername.startswith("sqlite") and url.database:
        db_path = Path(url.database)
        lock_path = db_path.with_suffix(".alembic.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(str(lock_path), timeout=60):
            cfg = _alembic_config(settings)
            command.upgrade(cfg, "head")
    else:
        # Postgres/MySQL: rely on alembic_version table + advisory locks (Batch 14 follow-up)
        cfg = _alembic_config(settings)
        command.upgrade(cfg, "head")
    try:
        with session_scope(settings) as session:
            recovered = recover_stale_runs(session, stale_after_seconds=60)
    except ModuleNotFoundError:
        if url.get_backend_name() == "sqlite":
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
        version="0.1.0",
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )
    app.state.limiter = limiter
    reset_rate_limit_storage()
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
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

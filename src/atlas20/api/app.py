"""FastAPI application factory for the Atlas20 research console."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlas20.api.routes.backtests import router as backtests_router
from atlas20.api.routes.compare import router as compare_router
from atlas20.api.routes.options import router as options_router
from atlas20.api.routes.overview import router as overview_router
from atlas20.api.routes.reports import router as reports_router
from atlas20.api.routes.runs import router as runs_router
from atlas20.api.routes.universe import router as universe_router


def create_app() -> FastAPI:
    app = FastAPI(title="Atlas20 Research Console API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(overview_router)
    app.include_router(options_router)
    app.include_router(runs_router)
    app.include_router(backtests_router)
    app.include_router(compare_router)
    app.include_router(universe_router)
    app.include_router(reports_router)
    return app


app = create_app()

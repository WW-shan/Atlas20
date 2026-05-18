"""Universe and data-health API routes."""

from fastapi import APIRouter

from atlas20.api.schemas import DataAlert, DataSource, UniverseTimelinePayload
from atlas20.api.services import (
    get_data_alerts,
    get_data_sources,
    get_universe_timeline,
    refresh_universe,
)

router = APIRouter(prefix="/api", tags=["universe"])


@router.get("/universe/timeline", response_model=UniverseTimelinePayload)
def get_timeline() -> UniverseTimelinePayload:
    return get_universe_timeline()


@router.get("/universe/sources", response_model=list[DataSource])
def get_sources() -> list[DataSource]:
    return get_data_sources()


@router.get("/universe/alerts", response_model=list[DataAlert])
def get_alerts() -> list[DataAlert]:
    return get_data_alerts()


@router.post("/universe/refresh")
def post_refresh() -> dict[str, str]:
    return refresh_universe()

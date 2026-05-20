"""Universe and data-health API routes."""

from fastapi import APIRouter, Depends, Request, Response
from sqlmodel import Session

from atlas20.api.dependencies.auth import verify_api_key
from atlas20.api.dependencies.ratelimit import limiter
from atlas20.api.repositories import get_session
from atlas20.api.schemas import DataAlert, DataSource, UniverseTimelinePayload
from atlas20.api.services import (
    get_data_alerts,
    get_data_sources,
    get_universe_refresh_status,
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


@router.post("/universe/refresh", status_code=202, dependencies=[Depends(verify_api_key)])
@limiter.limit("1/minute")
def post_refresh(request: Request, response: Response, session: Session = Depends(get_session)) -> dict[str, str]:
    del request
    del response
    return refresh_universe(session)


@router.get("/universe/refresh-status")
def get_refresh_status(session: Session = Depends(get_session)) -> dict[str, str | None]:
    return get_universe_refresh_status(session)

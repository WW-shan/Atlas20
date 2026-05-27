"""Universe and data-health API routes."""

from fastapi import APIRouter, Depends, Request, Response
from sqlmodel import Session

from atlas20.api.dependencies.auth import verify_api_key
from atlas20.api.dependencies.ratelimit import limiter
from atlas20.api.repositories import get_session
from atlas20.api.schemas import DataAlert, DataSource, UniverseTimelinePayload
from atlas20.api.services import ConsoleService, get_console_service

router = APIRouter(prefix="/api", tags=["universe"])


@router.get("/universe/timeline", response_model=UniverseTimelinePayload)
def get_timeline(service: ConsoleService = Depends(get_console_service)) -> UniverseTimelinePayload:
    return service.get_universe_timeline()


@router.get("/universe/sources", response_model=list[DataSource])
def get_sources(service: ConsoleService = Depends(get_console_service)) -> list[DataSource]:
    return service.get_data_sources()


@router.get("/universe/alerts", response_model=list[DataAlert])
def get_alerts(service: ConsoleService = Depends(get_console_service)) -> list[DataAlert]:
    return service.get_data_alerts()


@router.post("/universe/refresh", status_code=202, dependencies=[Depends(verify_api_key)])
@limiter.limit("1/minute")
def post_refresh(
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    service: ConsoleService = Depends(get_console_service),
) -> dict[str, str]:
    del request
    del response
    return service.refresh_universe(session)


@router.get("/universe/refresh-status")
def get_refresh_status(
    session: Session = Depends(get_session),
    service: ConsoleService = Depends(get_console_service),
) -> dict[str, str | None]:
    return service.get_universe_refresh_status(session)

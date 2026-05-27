"""Overview API routes."""

from fastapi import APIRouter, Depends

from atlas20.api.schemas import OverviewPayload
from atlas20.api.services import ConsoleService, get_console_service

router = APIRouter(prefix="/api", tags=["overview"])


@router.get("/overview", response_model=OverviewPayload, response_model_exclude_none=True)
def get_overview(service: ConsoleService = Depends(get_console_service)) -> OverviewPayload:
    return service.get_overview()

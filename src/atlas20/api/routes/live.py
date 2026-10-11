"""Read-only live research API routes."""

from fastapi import APIRouter, Depends, HTTPException, Request

from atlas20.api.schemas import LiveResearchPayload
from atlas20.api.services import ConsoleService, get_console_service

router = APIRouter(prefix="/api", tags=["live"])


@router.get("/live/research", response_model=LiveResearchPayload, response_model_exclude_none=True)
def get_live_research(
    request: Request,
    service: ConsoleService = Depends(get_console_service),
) -> LiveResearchPayload:
    unknown = sorted(request.query_params.keys())
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown query parameter(s): {', '.join(unknown)}")
    return service.get_live_research()

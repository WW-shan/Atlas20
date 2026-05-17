"""Overview API routes."""

from fastapi import APIRouter

from atlas20.api.schemas import OverviewResponse
from atlas20.api.services import get_overview_payload

router = APIRouter(prefix="/api", tags=["overview"])


@router.get("/overview", response_model=OverviewResponse)
def get_overview() -> OverviewResponse:
    return get_overview_payload()

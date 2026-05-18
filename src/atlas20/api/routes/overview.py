"""Overview API routes."""

from fastapi import APIRouter

from atlas20.api.schemas import OverviewPayload
from atlas20.api.services import get_overview as get_overview_payload

router = APIRouter(prefix="/api", tags=["overview"])


@router.get("/overview", response_model=OverviewPayload, response_model_exclude_none=True)
def get_overview() -> OverviewPayload:
    return get_overview_payload()

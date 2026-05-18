"""Strategy comparison API routes."""

from fastapi import APIRouter, Query

from atlas20.api.schemas import ChartRange, ComparePayload
from atlas20.api.services import get_compare as get_compare_payload

router = APIRouter(prefix="/api", tags=["compare"])


@router.get("/compare", response_model=ComparePayload)
def get_compare(
    ids: str = "",
    range_: ChartRange = Query(default="YTD", alias="range"),
) -> ComparePayload:
    return get_compare_payload([item for item in ids.split(",") if item], range_)

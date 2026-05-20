"""Strategy comparison API routes."""

from fastapi import APIRouter, HTTPException, Query, Request

from atlas20.api.schemas import ChartRange, ComparePayload
from atlas20.api.services import get_compare as get_compare_payload

router = APIRouter(prefix="/api", tags=["compare"])
ALLOWED_COMPARE_QUERY = {"ids", "range"}


@router.get("/compare", response_model=ComparePayload)
def get_compare(
    request: Request,
    ids: str = "",
    range_: ChartRange = Query(default="YTD", alias="range"),
) -> ComparePayload:
    unknown = sorted(key for key in request.query_params.keys() if key not in ALLOWED_COMPARE_QUERY)
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown query parameter(s): {', '.join(unknown)}")
    return get_compare_payload([item for item in ids.split(",") if item], range_)

"""Strategy comparison API routes."""

from fastapi import APIRouter, HTTPException, Query, Request

from atlas20.api.data_access._common import _format_display_name
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
    payload = get_compare_payload([item for item in ids.split(",") if item], range_)
    raw = payload.model_dump(mode="json")
    raw["strategies"] = [
        {"strategy": strategy, "display_name": _format_display_name(strategy)}
        for strategy in _compare_strategy_ids(payload)
    ]
    return ComparePayload.model_validate(raw)


def _compare_strategy_ids(payload: ComparePayload) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for row in payload.metrics.model_dump().values():
        for strategy in row:
            if strategy not in seen:
                seen.add(strategy)
                ordered.append(strategy)
    for point in payload.equity:
        for strategy in point.values:
            if strategy not in seen:
                seen.add(strategy)
                ordered.append(strategy)
    return ordered

"""Run API routes."""

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query

from atlas20.api import services
from atlas20.api.schemas import RunDetailPayload, RunRow, RunRowSummary, RunsListResponse

router = APIRouter(prefix="/api", tags=["runs"])


@router.get("/runs/queue", response_model=list[RunRowSummary], response_model_exclude_none=True)
def get_runs_queue() -> list[RunRowSummary]:
    return services.list_runs_queue()


@router.get("/runs", response_model=RunsListResponse, response_model_exclude_none=True)
def get_runs(
    q: str = "",
    chips: str = "",
    dateRange: Literal["7d", "30d", "90d", "ytd", "all"] = "30d",
    view: Literal["list", "grid"] = "list",
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=14, ge=1),
) -> dict[str, Any]:
    chip_values = [chip for chip in chips.split(",") if chip]
    items, total = services.list_runs(
        q=q,
        chips=chip_values,
        date_range=dateRange,
        view=view,
        page=page,
        page_size=pageSize,
    )
    return {
        "items": [item.model_dump(mode="json", by_alias=True, exclude_none=True) for item in items],
        "total": total,
        "page": page,
        "pageSize": pageSize,
    }


@router.get("/runs/{run_id}", response_model=RunRow, response_model_exclude_none=True)
def get_run(run_id: str) -> RunRow:
    run = services.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@router.get("/runs/{run_id}/detail", response_model=RunDetailPayload, response_model_exclude_none=True)
def get_run_detail(run_id: str) -> RunDetailPayload:
    detail = services.get_run_detail(run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="run not found")
    return detail


@router.post("/runs/{run_id}/favorite")
def post_run_favorite(run_id: str) -> dict[str, Any]:
    result = services.toggle_run_favorite(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="run not found")
    return result

"""Run API routes."""

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session

from atlas20.api import services
from atlas20.api.repositories import RunsRepo, get_session
from atlas20.api.schemas import HistoryFilter, RunDetailPayload, RunRow, RunRowSummary, RunsListResponse

router = APIRouter(prefix="/api", tags=["runs"])


@router.get("/runs/queue", response_model=list[RunRowSummary], response_model_exclude_none=True)
def get_runs_queue(session: Session = Depends(get_session)) -> list[RunRowSummary]:
    return services.list_runs_queue(session)


@router.get("/runs", response_model=RunsListResponse, response_model_exclude_none=True)
def get_runs(
    request: Request,
    session: Session = Depends(get_session),
    q: str = "",
    chips: str = "",
    dateRange: Literal["7d", "30d", "90d", "ytd", "all"] = "30d",
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=14, ge=1),
) -> dict[str, Any]:
    allowed = set(HistoryFilter.model_fields)
    unknown = sorted(key for key in request.query_params.keys() if key not in allowed)
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown query parameter(s): {', '.join(unknown)}")
    chip_values = [chip for chip in chips.split(",") if chip]
    items, total = services.list_runs(
        session,
        q=q,
        chips=chip_values,
        date_range=dateRange,
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
def get_run(run_id: str, session: Session = Depends(get_session)) -> RunRow:
    run = services.get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@router.get("/runs/{run_id}/detail", response_model=RunDetailPayload, response_model_exclude_none=True)
def get_run_detail(run_id: str, session: Session = Depends(get_session)) -> RunDetailPayload:
    detail = services.get_run_detail(session, run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="run not found")
    return detail


@router.post("/runs/{run_id}/favorite")
def post_run_favorite(run_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    result = services.toggle_run_favorite(session, run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="run not found")
    return result


@router.post("/runs/{run_id}/cancel", status_code=202)
def cancel_run(run_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    repo = RunsRepo(session)
    run = repo.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    if run.status == "cancelled":
        raise HTTPException(status_code=409, detail="run is already cancelled")
    if run.status == "completed":
        raise HTTPException(status_code=409, detail="run already completed; cannot cancel")
    if run.status == "failed":
        raise HTTPException(status_code=409, detail="run already failed; cannot cancel")
    repo.update(run_id, requested_cancel=True)
    return {"run_id": run_id, "requested_cancel": True}

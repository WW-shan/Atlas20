"""Constrained backtest API routes."""

from fastapi import APIRouter

from atlas20.api.runner import execute_backtest_request
from atlas20.api.schemas import BacktestRequest, RunStatus

router = APIRouter(prefix="/api", tags=["backtests"])


@router.get("/backtests")
def get_backtests() -> dict:
    return {"status": "ready"}


@router.post("/backtests/run", response_model=RunStatus)
def post_backtest(request: BacktestRequest) -> RunStatus:
    return execute_backtest_request(request)

"""Backtest API routes."""

from fastapi import APIRouter

from atlas20.api.schemas import BacktestConfig, RunRowSummary
from atlas20.api.services import register_new_backtest

router = APIRouter(prefix="/api", tags=["backtests"])


@router.post("/backtests/run", response_model=RunRowSummary, response_model_exclude_none=True)
def post_backtest(config: BacktestConfig) -> RunRowSummary:
    return register_new_backtest(config)

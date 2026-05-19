"""Backtest API routes."""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from atlas20.api.repositories import get_session
from atlas20.api.schemas import BacktestConfig, RunRowSummary
from atlas20.api.services import register_new_backtest

router = APIRouter(prefix="/api", tags=["backtests"])


@router.post("/backtests/run", response_model=RunRowSummary, response_model_exclude_none=True)
def post_backtest(config: BacktestConfig, session: Session = Depends(get_session)) -> RunRowSummary:
    return register_new_backtest(session, config)

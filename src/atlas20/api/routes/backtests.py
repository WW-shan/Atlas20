"""Backtest API routes."""

from fastapi import APIRouter, Depends, Header
from sqlmodel import Session

from atlas20.api.repositories import IdempotencyRepo, get_session
from atlas20.api.schemas import BacktestConfig, RunRowSummary
from atlas20.api.services import register_new_backtest

router = APIRouter(prefix="/api", tags=["backtests"])


@router.post("/backtests/run", response_model=RunRowSummary, response_model_exclude_none=True)
def post_backtest(
    config: BacktestConfig,
    session: Session = Depends(get_session),
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        pattern=r"^[A-Za-z0-9_-]+$",
        max_length=64,
    ),
) -> RunRowSummary:
    repo = IdempotencyRepo(session)
    if idempotency_key:
        cached = repo.get(idempotency_key)
        if cached is not None:
            return RunRowSummary.model_validate_json(cached.response_json)

    response = register_new_backtest(session, config)
    if idempotency_key:
        repo.store(idempotency_key, "POST", "/backtests/run", response.model_dump_json(), ttl_seconds=86400)
    return response

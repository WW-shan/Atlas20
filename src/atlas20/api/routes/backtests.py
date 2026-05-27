"""Backtest API routes."""

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlmodel import Session

from atlas20.api.dependencies.auth import verify_api_key
from atlas20.api.dependencies.ratelimit import limiter
from atlas20.api.repositories import IdempotencyRepo, get_session
from atlas20.api.schemas import BacktestConfig, RunRowSummary
from atlas20.api.services import ConsoleService, get_console_service

router = APIRouter(prefix="/api", tags=["backtests"])


@router.post(
    "/backtests/run",
    response_model=RunRowSummary,
    response_model_exclude_none=True,
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("10/minute")
def post_backtest(
    request: Request,
    response: Response,
    config: BacktestConfig,
    session: Session = Depends(get_session),
    service: ConsoleService = Depends(get_console_service),
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

    try:
        summary = service.register_new_backtest(session, config)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if idempotency_key:
        repo.store(idempotency_key, "POST", "/backtests/run", summary.model_dump_json(), ttl_seconds=86400)
    return summary

"""Backtest API routes."""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlmodel import Session

from atlas20.api.dependencies.auth import verify_api_key
from atlas20.api.dependencies.ratelimit import limiter
from atlas20.api.repositories import IdempotencyRepo, get_session
from atlas20.api.repositories.idempotency_repo import request_fingerprint
from atlas20.api.schemas import BacktestConfig, RunRowSummary
from atlas20.api.services import ConsoleService, get_console_service

router = APIRouter(prefix="/api", tags=["backtests"])
logger = logging.getLogger(__name__)

BACKTEST_RUN_PATH = "/api/backtests/run"
IDEMPOTENCY_TTL_SECONDS = 86400


@router.post(
    "/backtests/run",
    response_model=RunRowSummary,
    response_model_exclude_none=True,
)
@limiter.limit("10/minute")
def post_backtest(
    request: Request,
    response: Response,
    config: BacktestConfig,
    principal: str = Depends(verify_api_key),
    session: Session = Depends(get_session, scope="function"),
    service: ConsoleService = Depends(get_console_service),
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        pattern=r"^[A-Za-z0-9_-]+$",
        max_length=64,
    ),
) -> RunRowSummary:
    if not idempotency_key:
        return _register_backtest(service, session, config)

    repo = IdempotencyRepo(session)
    request_hash = request_fingerprint(
        principal=principal,
        method="POST",
        path=BACKTEST_RUN_PATH,
        body=config.model_dump(mode="json"),
    )
    claim = repo.claim(idempotency_key, method="POST", path=BACKTEST_RUN_PATH, request_hash=request_hash)
    if claim.status == "replay" and claim.response_json is not None:
        return RunRowSummary.model_validate_json(claim.response_json)
    if claim.status == "mismatch":
        raise HTTPException(status_code=422, detail="Idempotency-Key was already used for a different request")
    if claim.status != "claimed":
        raise HTTPException(status_code=409, detail="a request with this Idempotency-Key is still in progress")

    try:
        summary = _register_backtest(service, session, config)
        repo.complete(
            idempotency_key,
            request_hash=request_hash,
            response_json=summary.model_dump_json(),
            ttl_seconds=IDEMPOTENCY_TTL_SECONDS,
        )
        session.commit()
    except Exception:
        _release_claim(session, repo, idempotency_key, request_hash)
        raise
    return summary


def _register_backtest(service: ConsoleService, session: Session, config: BacktestConfig) -> RunRowSummary:
    try:
        return service.register_new_backtest(session, config)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _release_claim(session: Session, repo: IdempotencyRepo, key: str, request_hash: str) -> None:
    """Free the key after a failed request so the client can retry with it."""
    session.rollback()
    try:
        repo.release(key, request_hash=request_hash)
        session.commit()
    except Exception:
        session.rollback()
        logger.warning("could not release Idempotency-Key claim; it expires on its own", exc_info=True)

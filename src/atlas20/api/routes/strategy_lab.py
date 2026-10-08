"""Strategy Lab API routes."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlmodel import Session

from atlas20.api import services
from atlas20.api.config_adapter import validate_preset
from atlas20.api.dependencies.auth import verify_api_key
from atlas20.api.dependencies.ratelimit import limiter
from atlas20.api.repositories import get_session
from atlas20.api.schemas import StrategyLabBatchPayload, StrategyLabBatchResponse, StrategyLabMatrixRequest
from atlas20.api.settings import get_settings


router = APIRouter(prefix="/api", tags=["strategy-lab"])


@router.post(
    "/strategy-lab/batches",
    response_model=StrategyLabBatchResponse,
    status_code=202,
    dependencies=[Depends(verify_api_key)],
)
# One batch queues up to STRATEGY_LAB_MAX_RUNS (24) backtests, so it gets the
# tightest mutation budget (as /universe/refresh does). That keeps queued work
# per principal on the order of /backtests/run's 10 runs a minute.
@limiter.limit("1/minute")
def post_strategy_lab_batch(
    request: Request,
    response: Response,
    matrix: StrategyLabMatrixRequest,
    session: Session = Depends(get_session),
) -> StrategyLabBatchResponse:
    del request, response
    try:
        settings = get_settings()
        for preset in dict.fromkeys(matrix.presets):
            validate_preset(preset, settings)
        return services.submit_strategy_lab_batch(session, matrix)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/strategy-lab/batches/{batch_id}",
    response_model=StrategyLabBatchPayload,
)
def get_strategy_lab_batch(
    batch_id: str,
    session: Session = Depends(get_session),
) -> StrategyLabBatchPayload:
    return services.get_strategy_lab_batch(session, batch_id)

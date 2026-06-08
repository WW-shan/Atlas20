"""Strategy Lab API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from atlas20.api import services
from atlas20.api.dependencies.auth import verify_api_key
from atlas20.api.repositories import get_session
from atlas20.api.schemas import StrategyLabBatchPayload, StrategyLabBatchResponse, StrategyLabMatrixRequest


router = APIRouter(prefix="/api", tags=["strategy-lab"])


@router.post(
    "/strategy-lab/batches",
    response_model=StrategyLabBatchResponse,
    status_code=202,
    dependencies=[Depends(verify_api_key)],
)
def post_strategy_lab_batch(
    request: StrategyLabMatrixRequest,
    session: Session = Depends(get_session),
) -> StrategyLabBatchResponse:
    try:
        return services.submit_strategy_lab_batch(session, request)
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

"""Control option API routes."""

from fastapi import APIRouter

from atlas20.api.schemas import OptionsPayload
from atlas20.api.services import get_options_payload

router = APIRouter(prefix="/api", tags=["options"])


@router.get("/options", response_model=OptionsPayload)
def get_options() -> OptionsPayload:
    return get_options_payload()

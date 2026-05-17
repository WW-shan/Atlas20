"""Control option API routes."""

from fastapi import APIRouter

from atlas20.api.schemas import OptionsResponse
from atlas20.api.services import get_options_payload

router = APIRouter(prefix="/api", tags=["options"])


@router.get("/options", response_model=OptionsResponse)
def get_options() -> OptionsResponse:
    return get_options_payload()

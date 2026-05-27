"""Control option API routes."""

from fastapi import APIRouter, Depends

from atlas20.api.schemas import OptionsPayload
from atlas20.api.services import ConsoleService, get_console_service

router = APIRouter(prefix="/api", tags=["options"])


@router.get("/options", response_model=OptionsPayload)
def get_options(service: ConsoleService = Depends(get_console_service)) -> OptionsPayload:
    return service.get_options_payload()

"""Control option API routes."""

from typing import Any

from fastapi import APIRouter

from atlas20.api.services import get_options_payload

router = APIRouter(prefix="/api", tags=["options"])


@router.get("/options")
def get_options() -> dict[str, Any]:
    return get_options_payload()

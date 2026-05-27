"""SlowAPI limiter shared by mutating routes."""

import inspect

from fastapi import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import Response
from typing import cast

from atlas20.api._metrics import record_rate_limit_hit
from atlas20.api.settings import get_settings


def _key_func(request: Request) -> str:
    api_key = request.headers.get("X-API-Key") if get_settings().api_keys else None
    return api_key or get_remote_address(request)


limiter = Limiter(key_func=_key_func, headers_enabled=True)


def reset_rate_limit_storage() -> None:
    storage = getattr(limiter, "_storage", None)
    if storage is not None and hasattr(storage, "reset"):
        storage.reset()


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if route_path:
        record_rate_limit_hit(route_path)
    response = _rate_limit_exceeded_handler(request, exc)
    if inspect.isawaitable(response):
        return cast(Response, await response)
    return response

"""SlowAPI limiter shared by mutating routes."""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from atlas20.api.settings import get_settings


def _key_func(request: Request) -> str:
    api_key = request.headers.get("X-API-Key") if get_settings().api_keys else None
    return api_key or get_remote_address(request)


limiter = Limiter(key_func=_key_func)


def reset_rate_limit_storage() -> None:
    storage = getattr(limiter, "_storage", None)
    if storage is not None and hasattr(storage, "reset"):
        storage.reset()

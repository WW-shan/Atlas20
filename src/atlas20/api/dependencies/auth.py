"""API key authentication dependency."""

import hmac

from fastapi import Header, HTTPException

from atlas20.api.settings import get_settings


def verify_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> str:
    settings = get_settings()
    if not settings.api_keys:
        return "anonymous"
    if x_api_key is None:
        raise HTTPException(status_code=401, detail="X-API-Key header required")
    if not any(hmac.compare_digest(x_api_key, api_key) for api_key in settings.api_keys):
        raise HTTPException(status_code=401, detail="invalid API key")
    return x_api_key

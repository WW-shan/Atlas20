"""Small bounded retry helper for unauthenticated Bitget GET requests.

The live chain already fails closed on bad data, but a single transient TLS or
connection reset before the first order should not consume the day's primary
run.  These retries cover only transport and retryable HTTP status failures;
successful-but-invalid JSON still fails immediately.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Any

import requests

_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


def get_json_with_retries(
    session: requests.Session,
    url: str,
    *,
    params: Mapping[str, Any],
    timeout_seconds: float,
    max_retries: int = 4,
    retry_backoff_seconds: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """GET one public JSON object with bounded transport/5xx retries."""

    if max_retries < 1:
        raise ValueError("max_retries must be positive")
    if retry_backoff_seconds < 0.0:
        raise ValueError("retry_backoff_seconds must be non-negative")

    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = session.get(url, params=params, timeout=timeout_seconds)
        except requests.RequestException as exc:
            last_error = exc
            if attempt + 1 >= max_retries:
                raise
            sleep(retry_backoff_seconds * (2**attempt))
            continue

        if bool(getattr(response, "ok", False)):
            try:
                payload = response.json()
            except ValueError as exc:
                raise ValueError(f"Bitget {url} returned non-JSON payload") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"Bitget {url} returned an unexpected payload")
            return payload

        status = int(getattr(response, "status_code", 0) or 0)
        detail = str(getattr(response, "text", ""))[:200]
        error = requests.HTTPError(
            f"Bitget {url} HTTP {status or 'unknown'}: {detail}",
            response=response,  # type: ignore[arg-type]
        )
        last_error = error
        if status in _RETRY_STATUS_CODES and attempt + 1 < max_retries:
            sleep(retry_backoff_seconds * (2**attempt))
            continue
        raise error

    if last_error is not None:
        raise last_error
    raise requests.RequestException(f"Bitget {url} failed without a response")

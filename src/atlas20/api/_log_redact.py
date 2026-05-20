"""Sensitive-value redaction for structured logs and error events."""

from __future__ import annotations

import re
from typing import Any

REDACTED = "***REDACTED***"
SENSITIVE_KEYS = {"x-api-key", "authorization", "cookie", "secret_key", "secret", "api_key"}
SECRET_VALUE_PATTERN = re.compile(r"sk_[a-zA-Z0-9]{20,}")


def _is_sensitive_key(key: object) -> bool:
    return str(key).lower() in SENSITIVE_KEYS


def redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: REDACTED if _is_sensitive_key(key) else redact_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    if isinstance(value, str):
        return SECRET_VALUE_PATTERN.sub(REDACTED, value)
    return value


def redact_sensitive(_logger: object, _name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    return redact_value(event_dict)


def scrub_sensitive_headers(event: dict[str, Any], _hint: dict[str, Any] | None = None) -> dict[str, Any]:
    return redact_value(event)

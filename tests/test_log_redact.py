import json

import structlog

from atlas20.api._log_redact import REDACTED, redact_sensitive
from atlas20.api.logging_config import configure_logging
from atlas20.api.settings import Settings


def _redact(event: dict[str, object]) -> dict[str, object]:
    return redact_sensitive(None, "info", event)


def test_configured_structlog_redacts_sensitive_header_keys(capsys) -> None:
    configure_logging(Settings(log_format="json", log_level="INFO"))
    logger = structlog.get_logger("atlas20.api.access")

    logger.info("request", headers={"X-API-Key": "real-key", "Accept": "application/json"})
    captured = capsys.readouterr()

    event = json.loads(captured.out.strip())
    assert event["headers"] == {"X-API-Key": REDACTED, "Accept": "application/json"}


def test_redacts_nested_authorization_headers() -> None:
    event = _redact({"request": {"headers": {"Authorization": "Bearer abc"}}})

    assert event["request"]["headers"]["Authorization"] == REDACTED


def test_redacts_secret_value_patterns() -> None:
    event = _redact({"message": "token sk_abcdefghijklmnopqrstuvwxyz1234567890 leaked"})

    assert event["message"] == f"token {REDACTED} leaked"


def test_redacts_sensitive_keys_case_insensitively() -> None:
    event = _redact({"headers": {"x-api-key": "lower", "X-API-Key": "upper"}})

    assert event["headers"]["x-api-key"] == REDACTED
    assert event["headers"]["X-API-Key"] == REDACTED


def test_preserves_allowed_values_when_redacting_mixed_payload() -> None:
    event = _redact(
        {
            "secret_key": "dev-secret",
            "headers": {"Cookie": "session=abc", "User-Agent": "pytest"},
            "status": 200,
        }
    )

    assert event["secret_key"] == REDACTED
    assert event["headers"]["Cookie"] == REDACTED
    assert event["headers"]["User-Agent"] == "pytest"
    assert event["status"] == 200

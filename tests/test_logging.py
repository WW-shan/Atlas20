import json
import logging

from atlas20.api.logging_config import configure_logging
from atlas20.api.settings import Settings


def test_configure_logging_emits_json_with_required_fields(capsys):
    settings = Settings(log_format="json", log_level="INFO")
    configure_logging(settings)
    logger = logging.getLogger("atlas20.test")

    logger.info("hello", extra={"request_id": "req-1", "custom": "value"})
    captured = capsys.readouterr()

    payload = json.loads(captured.out.strip())
    assert payload["level"] == "INFO"
    assert payload["logger"] == "atlas20.test"
    assert payload["message"] == "hello"
    assert payload["request_id"] == "req-1"
    assert payload["custom"] == "value"
    assert "ts" in payload

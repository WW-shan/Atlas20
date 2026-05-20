import logging

from atlas20.api import logging_config
from atlas20.api.settings import Settings


def test_configure_logging_rotates_file_handler(tmp_path, monkeypatch) -> None:
    log_path = tmp_path / "api.log"
    monkeypatch.setattr(logging_config, "LOG_FILE_MAX_BYTES", 1024)
    settings = Settings(log_format="json", log_level="INFO", log_file_path=log_path)

    logging_config.configure_logging(settings)
    logger = logging.getLogger("atlas20.rotation")
    for index in range(80):
        logger.info("rotation line %s %s", index, "x" * 80)
    for handler in logging.getLogger().handlers:
        handler.flush()

    assert log_path.exists()
    assert log_path.with_name("api.log.1").exists()

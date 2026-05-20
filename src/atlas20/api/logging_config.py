"""Logging configuration for the Atlas20 API."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
from typing import Any

import structlog

from atlas20.api._log_redact import redact_sensitive
from atlas20.api.settings import Settings

LOG_FILE_MAX_BYTES = 50 * 1024 * 1024
LOG_FILE_BACKUP_COUNT = 10


def _uppercase_level(_: logging.Logger, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    level = event_dict.get("level")
    if isinstance(level, str):
        event_dict["level"] = level.upper()
    return event_dict


def configure_logging(settings: Settings) -> None:
    level = getattr(logging, settings.log_level)
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        _uppercase_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
        structlog.processors.format_exc_info,
        structlog.processors.EventRenamer("message"),
        redact_sensitive,
    ]

    if settings.log_format == "json":
        formatter: logging.Formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=[*shared_processors, structlog.stdlib.ExtraAdder()],
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                redact_sensitive,
                structlog.processors.JSONRenderer(),
            ],
        )
    else:
        formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handlers: list[logging.Handler] = [handler]
    if settings.log_file_path is not None:
        log_path = Path(settings.log_file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=LOG_FILE_MAX_BYTES,
            backupCount=LOG_FILE_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    for configured_handler in handlers:
        root_logger.addHandler(configured_handler)
    root_logger.setLevel(level)

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )

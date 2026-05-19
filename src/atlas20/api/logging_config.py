"""Logging configuration for the Atlas20 API."""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from atlas20.api.settings import Settings


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
    ]

    if settings.log_format == "json":
        formatter: logging.Formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=[*shared_processors, structlog.stdlib.ExtraAdder()],
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
        )
    else:
        formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
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

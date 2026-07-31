"""Logging helpers for applications built with Numa."""

from __future__ import annotations

import logging
import sys
from typing import TextIO

DEFAULT_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def configure_logging(
    level: str | int = "INFO",
    log_format: str = DEFAULT_FORMAT,
    stream: TextIO | None = None,
) -> None:
    """Configure console logging for the Numa namespace."""
    logger = logging.getLogger("numa")
    logger.setLevel(level)
    logger.propagate = False

    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(logging.Formatter(log_format))
    logger.handlers.clear()
    logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a logger using Python's standard logging interface."""
    return logging.getLogger(name)

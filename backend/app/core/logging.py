"""Structured-ish logging configuration."""

import logging
import sys

from app.core.config import settings

_CONFIGURED = False


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    # Explicit LOG_LEVEL wins; otherwise debug mode implies DEBUG.
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    if settings.app_debug and settings.log_level == "INFO":
        level = logging.DEBUG
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    root = logging.getLogger("blackhouse")
    root.handlers = [handler]
    root.setLevel(level)
    root.propagate = False
    # Quiet down noisy libraries
    for noisy in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(f"blackhouse.{name}")

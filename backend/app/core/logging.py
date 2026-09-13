"""Logging configuration: human-readable text or structured JSON.

Production platforms aggregate logs by parsing a stream, so ``LOG_FORMAT=json``
emits one JSON object per line with a stable field set. Local development keeps
the coloured-by-severity text format because it is far easier to read.

Every record carries ``request_id`` when one is present, which is what makes a
support ticket traceable: a customer reports an order, you find the request id
in the response header, and every log line for that request can be filtered out
of the aggregation UI.
"""

import json
import logging
import sys
from datetime import UTC, datetime

from app.core.config import settings

_CONFIGURED = False

# Fields that are part of every LogRecord and would otherwise be duplicated
# inside the JSON payload.
_RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """One JSON object per line, timestamps in RFC 3339 UTC.

    Extra fields passed via ``logger.info(..., extra={...})`` are promoted to
    top-level keys, which is what log aggregators index on. An exception is
    rendered into ``exception`` with the usual traceback text.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # Promote caller-supplied context (request_id, duration_ms, status, …).
        for key, value in record.__dict__.items():
            if key in _RESERVED or key in payload or key.startswith("_"):
                continue
            payload[key] = value

        # Never let a serialisation bug lose the log line itself.
        try:
            return json.dumps(payload, default=str, ensure_ascii=False)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            return json.dumps(
                {
                    "timestamp": payload["timestamp"],
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                    "unserialisable_extra": True,
                }
            )


def _resolve_level() -> int:
    """Explicit LOG_LEVEL wins; debug mode implies DEBUG unless overridden."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    if settings.app_debug and settings.log_level == "INFO":
        return logging.DEBUG
    return level


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    handler = logging.StreamHandler(sys.stdout)
    if settings.log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )

    root = logging.getLogger("blackhouse")
    root.handlers = [handler]
    root.setLevel(_resolve_level())
    # Propagating would double-log through the root logger's own handlers.
    root.propagate = False

    # Quiet down libraries that log per-request at INFO.
    for noisy in ("uvicorn.access", "httpx", "httpcore", "botocore", "boto3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True
    _init_sentry()


def _init_sentry() -> None:
    """Wire error tracking when a DSN is configured.

    Optional by design: the app must run identically without it, and the import
    failure path is silent so a slim image without the extra still boots.
    """
    if not settings.sentry_dsn:
        return
    try:
        import sentry_sdk  # optional dependency (observability extra)
    except ImportError:  # pragma: no cover - depends on installed extras
        get_logger("logging").warning(
            "SENTRY_DSN is set but sentry-sdk is not installed; "
            'install with: pip install "blackhouse-backend[observability]"'
        )
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        # Emails and phone numbers are personal data; do not ship them to a
        # third-party error tracker.
        send_default_pii=False,
        request_bodies="never",
    )
    get_logger("logging").info("sentry initialised (env=%s)", settings.app_env)


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(f"blackhouse.{name}")


def reset_logging() -> None:
    """Allow tests to reconfigure after monkeypatching settings."""
    global _CONFIGURED
    _CONFIGURED = False

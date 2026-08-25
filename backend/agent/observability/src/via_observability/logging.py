"""JSON structured logging configuration shared by all services."""

from __future__ import annotations

import logging
import os
from typing import Any

__all__ = ["configure_logging"]


class JsonFormatter(logging.Formatter):
    """Minimal JSON log formatter with request-context fields."""

    def format(self, record: logging.LogRecord) -> str:
        """Render one log record as a single-line JSON object.

        Args:
            record: The stdlib log record.

        Returns:
            JSON string containing standard fields plus any ``extra`` pairs
            and the current request context when present.
        """
        import json

        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        context = getattr(record, "context", None)
        if isinstance(context, dict):
            payload.update(context)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(service_name: str, *, level: str | None = None) -> None:
    """Configure root logging for one Via service.

    Installs the JSON formatter on a stream handler exactly once per
    process; safe to call from every service entry point.

    Args:
        service_name: Value stamped onto every record as ``service``.
        level: Log level name; falls back to ``VIA_LOG_LEVEL`` or INFO.
    """
    resolved = (level or os.environ.get("VIA_LOG_LEVEL", "INFO")).upper()
    root = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.handlers = [handler]
    root.setLevel(resolved)

    class _ServiceFilter(logging.Filter):
        """Stamp the service name onto every record passing through."""

        def __init__(self) -> None:
            """Initialize the filter."""
            super().__init__()

        def filter(self, record: logging.LogRecord) -> bool:
            """Attach the service context attribute.

            Args:
                record: Incoming record.

            Returns:
                Always True (never suppresses).
            """
            existing = getattr(record, "context", {})
            merged: dict[str, Any] = {
                "service": service_name,
                **(existing if isinstance(existing, dict) else {}),
            }
            record.context = merged
            return True

    root.addFilter(_ServiceFilter())

    # Third-party noise downgraded for readable local logs.
    for noisy in ("uvicorn.access", "botocore", "s3transfer"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

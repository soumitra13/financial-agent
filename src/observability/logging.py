"""
logging.py — Structured JSON logging for the Financial Agent System.

Usage:
    from src.observability.logging import get_logger
    log = get_logger(__name__)
    log.info("task_started", task_id=str(task_id), account_id=account_id)

All log records are emitted as single-line JSON to stdout, making them
trivially ingestible by Datadog, Loki, CloudWatch, or any log aggregator.

Format:
    {"ts": "2026-05-17T10:00:00Z", "level": "INFO", "logger": "src.agent.loop",
     "event": "task_started", "task_id": "...", ...}
"""

from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        # Merge any extra fields attached via log.info("msg", extra={...})
        for key, val in record.__dict__.items():
            if key not in {
                "args", "created", "exc_info", "exc_text", "filename",
                "funcName", "levelname", "levelno", "lineno", "message",
                "module", "msecs", "msg", "name", "pathname", "process",
                "processName", "relativeCreated", "stack_info", "taskName",
                "thread", "threadName",
            }:
                payload[key] = val
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """
    Call once at startup (in main.py lifespan and worker.py).
    Replaces the root handler with a JSON-over-stdout handler.
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove any existing handlers (uvicorn adds its own)
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    root.addHandler(handler)

    # Suppress noisy third-party loggers
    for noisy in ("uvicorn.access", "asyncio", "asyncpg"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> "BoundLogger":
    """Return a logger that supports keyword-argument structured fields."""
    return BoundLogger(logging.getLogger(name))


class BoundLogger:
    """
    Thin wrapper around stdlib Logger that supports structured keyword args:

        log.info("llm_call_complete", task_id="...", duration_ms=240)

    Extra kwargs are serialised into the JSON record via logging's `extra` dict.
    """

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    # Fields that LogRecord uses internally — passing these in `extra` raises KeyError
    _RESERVED = frozenset({
        "args", "created", "exc_info", "exc_text", "filename", "funcName",
        "levelname", "levelno", "lineno", "message", "module", "msecs", "msg",
        "name", "pathname", "process", "processName", "relativeCreated",
        "stack_info", "taskName", "thread", "threadName",
    })

    def _log(self, level: int, event: str, **kwargs: Any) -> None:
        # Prefix any reserved key with "x_" to avoid LogRecord collision
        safe = {(f"x_{k}" if k in self._RESERVED else k): v for k, v in kwargs.items()}
        self._logger.log(level, event, extra=safe, stacklevel=3)

    def debug(self, event: str, **kwargs: Any) -> None:
        self._log(logging.DEBUG, event, **kwargs)

    def info(self, event: str, **kwargs: Any) -> None:
        self._log(logging.INFO, event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        self._log(logging.WARNING, event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        self._log(logging.ERROR, event, **kwargs)

    def exception(self, event: str, **kwargs: Any) -> None:
        self._logger.exception(event, extra=kwargs, stacklevel=2)

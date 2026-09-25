"""JSON logging: one object per line on stdout, tagged with the id of the current request."""

import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

import orjson

# Id of the request being handled; set by RequestContextMiddleware (core.middleware).
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Attributes every LogRecord has; anything else on a record came in through `extra=`.
_RECORD_ATTRS = frozenset(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    """Formats a record as a JSON object: ts, level, logger, msg, extra fields, request_id."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RECORD_ATTRS and not key.startswith("_"):
                entry[key] = value
        if "request_id" not in entry and (request_id := request_id_var.get()) is not None:
            entry["request_id"] = request_id
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return orjson.dumps(entry, default=str).decode()


class _JsonHandler(logging.StreamHandler):
    """The handler of setup_logging; recognised on a second call and replaced, not doubled."""


def setup_logging(level: str) -> None:
    """Send every log record at `level` or above to stdout as JSON lines."""
    root = logging.getLogger()
    for handler in root.handlers[:]:
        if isinstance(handler, _JsonHandler):
            root.removeHandler(handler)
    handler = _JsonHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)
    # httpx logs every request at INFO; our own code logs what matters about upstream calls.
    logging.getLogger("httpx").setLevel(logging.WARNING)

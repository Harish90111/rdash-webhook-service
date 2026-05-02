"""Structured logging helpers for operational visibility."""

import json
import logging
from datetime import UTC, date, datetime


RESERVED_LOG_RECORD_FIELDS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}


class StructuredJSONFormatter(logging.Formatter):
    """Serialize log records to JSON while preserving structured context."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat().replace(
                "+00:00",
                "Z",
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "event": getattr(record, "event", record.getMessage()),
        }
        context = self._build_context(record)
        if context:
            payload["context"] = context
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=self._serialize_value, separators=(",", ":"), sort_keys=True)

    def _build_context(self, record: logging.LogRecord):
        context = {}
        for key, value in record.__dict__.items():
            if key in RESERVED_LOG_RECORD_FIELDS or key.startswith("_"):
                continue
            context[key] = self._serialize_value(value)
        return context

    @staticmethod
    def _serialize_value(value):
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, dict):
            return {
                str(key): StructuredJSONFormatter._serialize_value(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [StructuredJSONFormatter._serialize_value(item) for item in value]
        return str(value)

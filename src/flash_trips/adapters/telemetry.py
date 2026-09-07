import json
import logging
import re
from typing import Any

_STANDARD_RECORD_FIELDS = frozenset(logging.makeLogRecord({}).__dict__)
_EVENT_NAME = re.compile(r"[a-z][a-z0-9_.]{0,63}")
_ALLOWED_FIELDS = frozenset(
    {
        "component",
        "correlation_id",
        "duration_ms",
        "outcome",
        "request_id",
        "status_code",
    }
)


class RedactedJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event = (
            record.msg
            if isinstance(record.msg, str)
            and not record.args
            and _EVENT_NAME.fullmatch(record.msg)
            else "invalid_event_name"
        )
        payload: dict[str, Any] = {
            "event": event,
            "level": record.levelname,
        }
        for field, value in record.__dict__.items():
            if field not in _STANDARD_RECORD_FIELDS and field not in payload:
                payload[field] = value if field in _ALLOWED_FIELDS else "[REDACTED]"
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("flash_trips")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False

    handler = logging.StreamHandler()
    handler.setFormatter(RedactedJsonFormatter())
    logger.addHandler(handler)
    return logger

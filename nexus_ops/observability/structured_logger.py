"""Structured JSON Logging with Trace Correlation."""

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional


class StructuredJSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON with telemetry correlation."""

    def format(self, record: logging.LogRecord) -> str:
        log_payload = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Enrich with extra metadata if present
        for key in ("trace_id", "span_id", "session_id", "user_id", "order_id", "event_type"):
            if hasattr(record, key):
                log_payload[key] = getattr(record, key)

        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_payload)


def setup_logger(name: str = "nexus_ops", level: str = "INFO") -> logging.Logger:
    """Configures structured enterprise logger."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Avoid duplicate handlers
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredJSONFormatter())
        logger.addHandler(handler)

    return logger


logger = setup_logger()

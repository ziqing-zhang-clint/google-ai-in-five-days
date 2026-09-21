"""Structured JSON Logging with Trace Correlation, Intent-vs-Outcome Tracking, and PII Redaction."""

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from nexus_ops.observability.pii_redactor import pii_redactor


class StructuredJSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON with telemetry correlation and automatic PII redaction."""

    TRACKED_FIELDS = (
        "trace_id", "span_id", "session_id", "user_id", "order_id", "event_type",
        "planned_intent", "actual_outcome", "intent_satisfied", "discrepancy_reason",
        "selected_model", "complexity_score"
    )

    def format(self, record: logging.LogRecord) -> str:
        # Scrub message with PII redactor
        clean_message = pii_redactor.redact(record.getMessage())

        log_payload = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": clean_message,
        }

        # Enrich with extra telemetry metadata (with PII scrubbing)
        for key in self.TRACKED_FIELDS:
            if hasattr(record, key):
                val = getattr(record, key)
                log_payload[key] = pii_redactor.redact_data(val)

        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_payload)


class NexusLogger(logging.Logger):
    """Extended logger providing intent vs outcome operational logging."""

    def log_intent_vs_outcome(
        self,
        planned_intent: str,
        actual_outcome: str,
        intent_satisfied: bool,
        discrepancy_reason: Optional[str] = None,
        session_id: Optional[str] = None,
        run_id: Optional[str] = None,
        **kwargs
    ):
        """Explicitly logs intent versus actual outcome for operational audit and trajectory evaluation."""
        extra = {
            "event_type": "INTENT_VS_OUTCOME",
            "planned_intent": planned_intent,
            "actual_outcome": actual_outcome,
            "intent_satisfied": intent_satisfied,
            "discrepancy_reason": discrepancy_reason or ("None" if intent_satisfied else "Deviation detected"),
            "session_id": session_id or "unknown",
            "trace_id": run_id or "unknown",
            **kwargs
        }
        status_text = "SATISFIED" if intent_satisfied else "DISCREPANCY/UNSATISFIED"
        self.info(
            f"Intent vs Actual Outcome Audit: planned='{planned_intent}' | actual='{actual_outcome}' | status={status_text}",
            extra=extra
        )


logging.setLoggerClass(NexusLogger)


def setup_logger(name: str = "nexus_ops", level: str = "INFO") -> NexusLogger:
    """Configures structured enterprise logger."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Avoid duplicate handlers
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredJSONFormatter())
        logger.addHandler(handler)

    return logger  # type: ignore[return-value]


logger = setup_logger()

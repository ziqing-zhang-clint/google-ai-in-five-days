"""Unit tests for Observability, OpenTelemetry GenAI Spans, Structured Logging, and Metrics."""

import json
import logging
import pytest
from nexus_ops.observability.otel_tracer import otel_tracer
from nexus_ops.observability.structured_logger import StructuredJSONFormatter, setup_logger
from nexus_ops.observability.metrics import MetricsCollector


def test_otel_orchestration_span():
    with otel_tracer.trace_orchestration_step(
        session_id="sess-otel-1",
        user_id="user-1",
        step_index=0,
        agent_name="test_coordinator"
    ) as span:
        assert span is not None
        assert span.is_recording()


def test_otel_tool_execution_span():
    params = {"order_id": "ORD-901", "secret_token": "SENSITIVE_12345", "amount": 50.0}
    with otel_tracer.trace_tool_execution("test_tool", params) as span:
        assert span is not None
        assert span.is_recording()


def test_otel_llm_inference_span():
    with otel_tracer.trace_llm_inference("gemini-2.5-pro", "Sample prompt") as span:
        assert span is not None
        assert span.is_recording()


def test_structured_json_logging():
    formatter = StructuredJSONFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Operational dispatch initiated",
        args=(),
        exc_info=None
    )
    record.order_id = "ORD-901"
    record.trace_id = "TRC-888"

    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test_logger"
    assert parsed["message"] == "Operational dispatch initiated"
    assert parsed["order_id"] == "ORD-901"
    assert parsed["trace_id"] == "TRC-888"
    assert "timestamp" in parsed


def test_metrics_collector():
    m = MetricsCollector()
    assert m.total_requests == 0
    assert m.successful_resolutions == 0

    m.record_request()
    m.record_request()
    m.record_tool_call("carrier_track")
    m.record_tool_call("carrier_track")
    m.record_tool_call("payment_refund")
    m.record_resolution(success=True, hitl=False, refund_amount=45.50)
    m.record_resolution(success=False, hitl=True, refund_amount=0.0)
    m.record_circuit_breaker()

    summary = m.get_summary()
    assert summary["total_requests"] == 2
    assert summary["successful_resolutions"] == 1
    assert summary["hitl_escalations"] == 1
    assert summary["success_rate_percent"] == 50.0
    assert summary["total_refunded_usd"] == 45.50
    assert summary["circuit_breaker_trips"] == 1
    assert summary["tool_invocations"]["carrier_track"] == 2
    assert summary["tool_invocations"]["payment_refund"] == 1

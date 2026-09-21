"""OpenTelemetry Tracing with GenAI Semantic Conventions."""

import time
from typing import Any, Dict, Optional
from contextlib import contextmanager
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
from nexus_ops.config import settings

# Initialize Tracer Provider
resource = Resource.create({"service.name": settings.otel_service_name, "environment": settings.environment})
provider = TracerProvider(resource=resource)
tracer = provider.get_tracer(settings.otel_service_name)


class NexusTracer:
    """Enterprise OpenTelemetry GenAI Instrumentation wrapper."""

    def __init__(self):
        self._tracer = tracer

    @contextmanager
    def trace_orchestration_step(
        self,
        session_id: str,
        user_id: str,
        step_index: int,
        agent_name: str
    ):
        """Traces a high-level agent orchestration iteration."""
        with self._tracer.start_as_current_span(f"agent.step.{step_index}") as span:
            span.set_attribute("gen_ai.system", "google_adk")
            span.set_attribute("gen_ai.agent.name", agent_name)
            span.set_attribute("session.id", session_id)
            span.set_attribute("user.id", user_id)
            span.set_attribute("step.index", step_index)
            start_time = time.time()
            try:
                yield span
            finally:
                duration_ms = (time.time() - start_time) * 1000.0
                span.set_attribute("gen_ai.latency_ms", duration_ms)

    @contextmanager
    def trace_tool_execution(
        self,
        tool_name: str,
        parameters: Dict[str, Any]
    ):
        """Traces a discrete tool execution span with GenAI attributes."""
        with self._tracer.start_as_current_span(f"tool.{tool_name}") as span:
            span.set_attribute("gen_ai.system", "google_adk")
            span.set_attribute("gen_ai.tool.name", tool_name)
            # Store sanitized parameter string representation
            param_repr = str({k: v for k, v in parameters.items() if "token" not in k.lower() and "key" not in k.lower()})
            span.set_attribute("gen_ai.tool.parameters", param_repr[:200])

            start = time.time()
            try:
                yield span
            finally:
                span.set_attribute("gen_ai.tool.duration_ms", (time.time() - start) * 1000.0)

    @contextmanager
    def trace_llm_inference(
        self,
        model_name: str,
        prompt_text: str
    ):
        """Traces an LLM generation call."""
        with self._tracer.start_as_current_span("llm.generate") as span:
            span.set_attribute("gen_ai.system", "google_adk")
            span.set_attribute("gen_ai.request.model", model_name)
            span.set_attribute("gen_ai.prompt_length", len(prompt_text))
            start = time.time()
            try:
                yield span
            finally:
                span.set_attribute("gen_ai.latency_ms", (time.time() - start) * 1000.0)


otel_tracer = NexusTracer()

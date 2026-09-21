"""Operational Metrics Counter and Cost Attribution."""

from typing import Dict, Any
from datetime import datetime


class MetricsCollector:
    """Collects runtime operational performance and business KPIs."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.total_requests = 0
        self.successful_resolutions = 0
        self.hitl_escalations = 0
        self.tool_invocations: Dict[str, int] = {}
        self.total_refunded_usd = 0.0
        self.circuit_breaker_trips = 0
        self.start_time = datetime.utcnow().isoformat()

    def record_request(self):
        self.total_requests += 1

    def record_tool_call(self, tool_name: str):
        self.tool_invocations[tool_name] = self.tool_invocations.get(tool_name, 0) + 1

    def record_resolution(self, success: bool, hitl: bool = False, refund_amount: float = 0.0):
        if success:
            self.successful_resolutions += 1
        if hitl:
            self.hitl_escalations += 1
        if refund_amount > 0:
            self.total_refunded_usd += refund_amount

    def record_circuit_breaker(self):
        self.circuit_breaker_trips += 1

    def get_summary(self) -> Dict[str, Any]:
        success_rate = (
            (self.successful_resolutions / self.total_requests * 100.0)
            if self.total_requests > 0
            else 0.0
        )
        return {
            "uptime_start": self.start_time,
            "total_requests": self.total_requests,
            "successful_resolutions": self.successful_resolutions,
            "success_rate_percent": round(success_rate, 2),
            "hitl_escalations": self.hitl_escalations,
            "total_refunded_usd": round(self.total_refunded_usd, 2),
            "circuit_breaker_trips": self.circuit_breaker_trips,
            "tool_invocations": self.tool_invocations
        }


metrics = MetricsCollector()

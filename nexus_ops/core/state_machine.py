"""State Machine and Circuit Breaker Loop Protection."""

from typing import Any, Dict, List, Optional
from nexus_ops.config import settings
from nexus_ops.observability.structured_logger import logger
from nexus_ops.observability.metrics import metrics


class CircuitBreakerError(Exception):
    """Raised when an agent iteration ceiling is breached."""
    pass


class OperationalStateMachine:
    """Controls the 5-step operational loop and prevents runaway execution."""

    def __init__(self, max_steps: int = settings.max_agent_iterations):
        self.max_steps = max_steps

    def validate_step(self, current_step: int, run_id: str):
        """Checks if current execution step exceeds circuit breaker threshold."""
        if current_step >= self.max_steps:
            metrics.record_circuit_breaker()
            logger.error(f"Circuit Breaker Tripped! Run {run_id} reached step limit {self.max_steps}.")
            raise CircuitBreakerError(
                f"Execution aborted by Circuit Breaker: Exceeded maximum allowed iterations ({self.max_steps})."
            )

    def detect_repetitive_loop(self, tool_call_history: List[str], max_consecutive: int = 3) -> bool:
        """Detects if an agent is stuck calling the exact same tool repeatedly."""
        if len(tool_call_history) < max_consecutive:
            return False
        recent = tool_call_history[-max_consecutive:]
        return len(set(recent)) == 1


state_machine = OperationalStateMachine()

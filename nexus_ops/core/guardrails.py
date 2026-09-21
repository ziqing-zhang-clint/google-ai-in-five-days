"""Security Guardrails and Confused Deputy Defenses."""

import re
from typing import Tuple, Optional
from nexus_ops.config import settings
from nexus_ops.observability.structured_logger import logger


class SecurityGuardrails:
    """Enterprise policy and security interceptor."""

    INJECTION_PATTERNS = [
        r"ignore (all )?previous instructions",
        r"system prompt override",
        r"grant admin permissions",
        r"cat /etc/passwd",
        r"\.\./\.\.",
        r"bypass security"
    ]

    def validate_user_input(self, user_prompt: str) -> Tuple[bool, Optional[str]]:
        """Scans user input for adversarial prompt injection or traversal attacks."""
        for pattern in self.INJECTION_PATTERNS:
            if re.search(pattern, user_prompt, re.IGNORECASE):
                logger.warning(f"Security Alert: Malicious prompt injection pattern detected: '{pattern}'")
                return False, f"Request rejected by Security Guardrail: Prohibited instruction pattern detected."
        return True, None

    def evaluate_hitl_requirement(
        self,
        action_name: str,
        amount_usd: float = 0.0,
        customer_tier: str = "STANDARD"
    ) -> Tuple[bool, str]:
        """Evaluates whether an intended action requires mandatory Human-In-The-Loop approval."""
        if action_name == "REFUND" and amount_usd >= settings.hitl_mandatory_threshold_usd:
            return True, f"High-Value Financial Action: Refund of ${amount_usd:.2f} exceeds ${settings.hitl_mandatory_threshold_usd:.2f} auto-threshold."

        if action_name == "CANCEL_ORDER" and customer_tier == "ENTERPRISE" and amount_usd >= 1000.0:
            return True, f"High-Stakes Contract: Cancellation of Enterprise order (${amount_usd:.2f}) requires Account Executive sign-off."

        return False, "Autonomous execution authorized under policy limits."


guardrails = SecurityGuardrails()

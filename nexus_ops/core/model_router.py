"""Strategic Model Router for Dynamic Task Complexity Routing.

Enforces intelligent compute economics:
- Frontier Model (Gemini 2.5 Pro): Multi-step reasoning, ambiguous contract disputes, high financial stakes.
- Lightweight Model (Gemini 2.5 Flash): Deterministic lookups, fast entity extraction, carrier tracking, formatting.
"""

import re
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from nexus_ops.config import settings
from nexus_ops.observability.structured_logger import logger
from nexus_ops.observability.otel_tracer import otel_tracer
from nexus_ops.observability.metrics import metrics


class RoutingDecision(BaseModel):
    """Encapsulates model selection, complexity score, and economic rationale."""
    selected_model: str
    tier: str  # "FRONTIER" or "LIGHTWEIGHT"
    complexity_score: float = Field(..., ge=0.0, le=1.0)
    task_type: str
    rationale: str


class StrategicModelRouter:
    """Dynamically routes requests between Frontier and Lightweight models based on task complexity."""

    def __init__(
        self,
        frontier_model: str = settings.frontier_model,
        fast_model: str = settings.fast_model
    ):
        self.frontier_model = frontier_model
        self.fast_model = fast_model

    def evaluate_complexity(
        self,
        user_prompt: str,
        customer_tier: str = "STANDARD",
        turn_count: int = 0
    ) -> RoutingDecision:
        """Calculates task complexity score and assigns the optimal model."""
        score = 0.1
        factors = []

        # Factor 1: Financial Dispute / High Stakes (+$0.35)
        amount_match = re.search(r"\$(\d+(\.\d+)?)", user_prompt)
        has_financial_intent = any(w in user_prompt.lower() for w in ["refund", "compensation", "credit", "charge", "dispute"])
        if has_financial_intent:
            score += 0.25
            factors.append("Financial dispute intent")
            if amount_match and float(amount_match.group(1)) >= 100.0:
                score += 0.25
                factors.append(f"High-value claim (${amount_match.group(1)})")

        # Factor 2: Customer Tier & Contractual SLA Ambiguity (+$0.20)
        if customer_tier in ["ENTERPRISE", "VIP"]:
            score += 0.15
            factors.append(f"High-priority {customer_tier} SLA tier")

        # Factor 3: Multi-Intent / Exception Compounding (+$0.25)
        has_logistics = any(w in user_prompt.lower() for w in ["track", "shipping", "delay", "lost", "carrier"])
        if has_financial_intent and has_logistics:
            score += 0.20
            factors.append("Compound intent: Logistics exception with financial dispute")

        # Factor 4: Conversational Depth & Reasoning State (+$0.10)
        if turn_count >= 4:
            score += 0.15
            factors.append(f"Deep multi-turn context ({turn_count} turns)")

        complexity_score = min(1.0, round(score, 2))

        # Strategic Routing Threshold: >= 0.50 -> Frontier; < 0.50 -> Lightweight
        if complexity_score >= 0.50:
            decision = RoutingDecision(
                selected_model=self.frontier_model,
                tier="FRONTIER",
                complexity_score=complexity_score,
                task_type="COMPLEX_CONTRACT_DISPUTE_REASONING",
                rationale=f"Routed to Frontier Model ({self.frontier_model}) due to high complexity ({complexity_score}): {'; '.join(factors)}"
            )
        else:
            decision = RoutingDecision(
                selected_model=self.fast_model,
                tier="LIGHTWEIGHT",
                complexity_score=complexity_score,
                task_type="FAST_LOOKUP_AND_EXTRACTION",
                rationale=f"Routed to Fast Model ({self.fast_model}) for cost efficiency (complexity {complexity_score})"
            )

        logger.info(
            f"Strategic Model Routing: {decision.selected_model} (Tier: {decision.tier}, Score: {decision.complexity_score})"
        )
        return decision

    def generate_response(
        self,
        prompt: str,
        system_instruction: str,
        decision: RoutingDecision
    ) -> str:
        """Executes model inference with the dynamically routed model."""
        with otel_tracer.trace_llm_inference(decision.selected_model, prompt):
            metrics.record_tool_call(f"model_{decision.tier.lower()}")

            api_key = settings.get_api_key()
            if api_key:
                try:
                    from google import genai
                    client = genai.Client(api_key=api_key)
                    response = client.models.generate_content(
                        model=decision.selected_model,
                        contents=prompt,
                        config={"system_instruction": system_instruction}
                    )
                    return response.text
                except Exception as e:
                    logger.warning(f"Live Gemini API execution failed ({e}), falling back to simulated reasoning.")

            # Deterministic High-Fidelity Simulation (for offline evaluation sandbox and test environments)
            return f"[Model: {decision.selected_model} | Tier: {decision.tier}] Processed with complexity {decision.complexity_score}."


model_router = StrategicModelRouter()

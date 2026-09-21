"""Enterprise Policy & SLA Rules Engine Tool."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from nexus_ops.data.mock_db import db
from nexus_ops.config import settings


class PolicyEvaluationInput(BaseModel):
    order_id: str = Field(..., description="Target order identifier.")
    customer_id: str = Field(..., description="Target customer identifier.")
    dispute_category: str = Field(
        ...,
        description="Category: 'TRANSIT_DELAY', 'DAMAGED_GOODS', 'WRONG_ITEM', 'BUYER_REMORSE', 'DEFECTIVE'."
    )
    requested_compensation_usd: float = Field(default=0.0, description="Customer-requested reimbursement amount.")


class PolicyEvaluationOutput(BaseModel):
    decision: str  # APPROVED, PARTIALLY_APPROVED, REQUIRES_HITL_ESCALATION, REJECTED
    authorized_amount_usd: float
    requires_return: bool
    sla_priority: str
    customer_tier: str
    policy_clauses_applied: List[str]
    rationale: str


def evaluate_dispute_policy(
    order_id: str,
    customer_id: str,
    dispute_category: str,
    requested_compensation_usd: float = 0.0
) -> Dict[str, Any]:
    """Evaluates enterprise contractual dispute and refund policies.

    Encapsulates:
    - Customer tier service level agreements (ENTERPRISE, VIP, STANDARD).
    - Transit exception rules & goodwill courtesy compensation ceilings.
    - Mandatory supervisor escalation thresholds.

    Preconditions: order_id and customer_id must be valid.
    Postconditions: Returns binding policy authorization decision and rationale.
    """
    customer = db.customers.get(customer_id.strip())
    order = db.orders.get(order_id.strip())

    if not customer:
        return PolicyEvaluationOutput(
            decision="REJECTED",
            authorized_amount_usd=0.0,
            requires_return=False,
            sla_priority="STANDARD",
            customer_tier="UNKNOWN",
            policy_clauses_applied=["POL-ERR-001: Customer Profile Not Found"],
            rationale=f"Customer ID '{customer_id}' does not exist in master CRM."
        ).model_dump()

    tier = customer.tier.upper()
    clauses: List[str] = []
    category = dispute_category.strip().upper()

    # Rule 1: High-stakes mandatory escalation threshold
    if requested_compensation_usd >= settings.hitl_mandatory_threshold_usd:
        clauses.append(f"POL-FIN-401: Requests >= ${settings.hitl_mandatory_threshold_usd} require Human-In-The-Loop review.")
        return PolicyEvaluationOutput(
            decision="REQUIRES_HITL_ESCALATION",
            authorized_amount_usd=0.0,
            requires_return=True,
            sla_priority="HIGH" if tier in {"ENTERPRISE", "VIP"} else "STANDARD",
            customer_tier=tier,
            policy_clauses_applied=clauses,
            rationale=f"Requested amount (${requested_compensation_usd:.2f}) exceeds autonomous agent authorization limit."
        ).model_dump()

    # Rule 2: Transit Exception / Carrier Delay
    if category == "TRANSIT_DELAY":
        clauses.append("POL-LOG-102: Carrier Transit Exception Compensation Clause.")
        if tier == "ENTERPRISE":
            clauses.append("POL-SLA-ENT: Enterprise SLA guarantees zero-downtime courtesy credit.")
            return PolicyEvaluationOutput(
                decision="APPROVED",
                authorized_amount_usd=min(requested_compensation_usd, 50.0) if requested_compensation_usd > 0 else 50.0,
                requires_return=False,
                sla_priority="URGENT_ENTERPRISE",
                customer_tier=tier,
                policy_clauses_applied=clauses,
                rationale="Enterprise tier customer delayed in transit. Authorized automatic $50.00 service credit."
            ).model_dump()
        else:
            return PolicyEvaluationOutput(
                decision="APPROVED",
                authorized_amount_usd=25.0,
                requires_return=False,
                sla_priority="STANDARD",
                customer_tier=tier,
                policy_clauses_applied=clauses,
                rationale="Standard transit delay courtesy credit of $25.00 authorized."
            ).model_dump()

    # Rule 3: Damaged or Defective Goods
    if category in {"DAMAGED_GOODS", "DEFECTIVE"}:
        order_total = order.total_amount if order else 100.0
        claim_amount = requested_compensation_usd if requested_compensation_usd > 0 else order_total

        if tier == "ENTERPRISE":
            clauses.append("POL-RET-ENT: Enterprise direct replacement without mandatory return.")
            return PolicyEvaluationOutput(
                decision="APPROVED",
                authorized_amount_usd=min(claim_amount, settings.auto_refund_limit_usd),
                requires_return=False,
                sla_priority="EXPEDITED",
                customer_tier=tier,
                policy_clauses_applied=clauses,
                rationale="Enterprise Tier defect claim: Authorized immediate refund under $100 cap without return."
            ).model_dump()
        elif tier == "VIP":
            clauses.append("POL-RET-VIP: VIP expedited claim with photo verification.")
            return PolicyEvaluationOutput(
                decision="APPROVED",
                authorized_amount_usd=min(claim_amount, settings.auto_refund_limit_usd),
                requires_return=False,
                sla_priority="HIGH",
                customer_tier=tier,
                policy_clauses_applied=clauses,
                rationale="VIP Tier claim: Authorized refund under $100 limit."
            ).model_dump()
        else:
            clauses.append("POL-RET-STD: Standard merchandise return authorization required.")
            return PolicyEvaluationOutput(
                decision="PARTIALLY_APPROVED",
                authorized_amount_usd=min(claim_amount, 50.0),
                requires_return=True,
                sla_priority="STANDARD",
                customer_tier=tier,
                policy_clauses_applied=clauses,
                rationale="Standard Tier claim: Requires RMA return authorization before final balance settlement."
            ).model_dump()

    # Default fallback
    clauses.append("POL-GEN-099: Standard 30-Day Policy Review.")
    return PolicyEvaluationOutput(
        decision="PARTIALLY_APPROVED",
        authorized_amount_usd=min(requested_compensation_usd, 30.0),
        requires_return=True,
        sla_priority="STANDARD",
        customer_tier=tier,
        policy_clauses_applied=clauses,
        rationale="General dispute: Discretionary courtesy credit up to $30.00 authorized."
    ).model_dump()

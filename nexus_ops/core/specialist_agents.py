"""Specialist Agents for Bounded Domain Operations."""

from typing import Any, Dict, Optional
from nexus_ops.tools.order_db_tool import lookup_order_details, update_order_status
from nexus_ops.tools.carrier_logistics_tool import track_carrier_shipment, open_carrier_investigation
from nexus_ops.tools.payment_gateway_tool import lookup_payment_details, execute_order_refund
from nexus_ops.tools.policy_engine_tool import evaluate_dispute_policy
from nexus_ops.observability.otel_tracer import otel_tracer
from nexus_ops.observability.structured_logger import logger
from nexus_ops.observability.metrics import metrics


class LogisticsSpecialistAgent:
    """Specialist sub-agent governing shipment routing, carrier tracing, and transit delays."""

    name = "specialist:logistics"

    def investigate(self, order_id: str) -> Dict[str, Any]:
        with otel_tracer.trace_tool_execution(f"{self.name}.investigate", {"order_id": order_id}):
            metrics.record_tool_call("logistics_investigate")
            logger.info(f"LogisticsSpecialist investigating order {order_id}")

            order_res = lookup_order_details(order_id)
            if not order_res["found"]:
                return {"status": "ERROR", "message": f"Order {order_id} not found."}

            tracking_num = order_res.get("tracking_number")
            if not tracking_num:
                return {
                    "status": "UNSHIPPED",
                    "order_status": order_res.get("status"),
                    "message": "Order has not yet been assigned a carrier tracking number."
                }

            tracking_res = track_carrier_shipment(tracking_num)
            if not tracking_res["found"]:
                return {"status": "ERROR", "message": f"Tracking number {tracking_num} not recognized."}

            assessment = {
                "status": "SUCCESS",
                "carrier": tracking_res.get("carrier"),
                "carrier_status": tracking_res.get("status"),
                "has_exception": tracking_res.get("has_transit_exception", False),
                "estimated_delivery": tracking_res.get("estimated_delivery"),
                "actual_delivery": tracking_res.get("actual_delivery"),
                "recent_events": tracking_res.get("events", [])[-2:]
            }

            # If delayed, automatically trigger carrier tracing ticket
            if tracking_res.get("has_transit_exception"):
                ticket = open_carrier_investigation(tracking_num, "WEATHER_DELAY", "EXPEDITED")
                assessment["carrier_ticket"] = ticket

            return assessment


class BillingSpecialistAgent:
    """Specialist sub-agent governing financial transactions, dispute ledgering, and refund execution."""

    name = "specialist:billing"

    def resolve_dispute(
        self,
        order_id: str,
        customer_id: str,
        dispute_category: str,
        requested_amount: float,
        authorization_token: str
    ) -> Dict[str, Any]:
        with otel_tracer.trace_tool_execution(f"{self.name}.resolve_dispute", {"order_id": order_id, "amount": requested_amount}):
            metrics.record_tool_call("billing_resolve_dispute")
            logger.info(f"BillingSpecialist evaluating dispute for {order_id}, requested: ${requested_amount:.2f}")

            # 1. Inspect Policy
            policy_res = evaluate_dispute_policy(
                order_id=order_id,
                customer_id=customer_id,
                dispute_category=dispute_category,
                requested_compensation_usd=requested_amount
            )

            decision = policy_res["decision"]
            auth_amount = policy_res["authorized_amount_usd"]

            if decision == "REJECTED":
                return {
                    "status": "REJECTED",
                    "authorized_amount": 0.0,
                    "policy_decision": policy_res,
                    "message": f"Dispute rejected under enterprise policy: {policy_res['rationale']}"
                }

            if decision == "REQUIRES_HITL_ESCALATION":
                metrics.record_resolution(success=False, hitl=True)
                return {
                    "status": "ESCALATED_TO_HUMAN",
                    "authorized_amount": 0.0,
                    "policy_decision": policy_res,
                    "message": f"Escalated to Supervisor review queue: {policy_res['rationale']}"
                }

            # 2. Execute Refund under approved authorization
            refund_res = execute_order_refund(
                order_id=order_id,
                amount=auth_amount,
                reason=f"Dispute Resolution: {dispute_category}",
                authorization_token=authorization_token
            )

            if refund_res["success"]:
                metrics.record_resolution(success=True, refund_amount=auth_amount)
                # Update order status in ERP
                update_order_status(
                    order_id=order_id,
                    new_status="REFUNDED" if refund_res["remaining_balance"] <= 0 else "DISPUTED",
                    reason=f"Refund {refund_res.get('refund_id')} of ${auth_amount:.2f} executed."
                )

            return {
                "status": "EXECUTED" if refund_res["success"] else "FAILED",
                "authorized_amount": auth_amount,
                "refund_details": refund_res,
                "policy_decision": policy_res
            }


class PolicyComplianceAgent:
    """Specialist sub-agent ensuring enterprise SLA guarantees and contract alignment."""

    name = "specialist:compliance"

    def check_sla(self, customer_id: str, order_id: str, category: str) -> Dict[str, Any]:
        with otel_tracer.trace_tool_execution(f"{self.name}.check_sla", {"customer_id": customer_id}):
            metrics.record_tool_call("compliance_check_sla")
            return evaluate_dispute_policy(
                order_id=order_id,
                customer_id=customer_id,
                dispute_category=category,
                requested_compensation_usd=0.0
            )


logistics_specialist = LogisticsSpecialistAgent()
billing_specialist = BillingSpecialistAgent()
compliance_specialist = PolicyComplianceAgent()

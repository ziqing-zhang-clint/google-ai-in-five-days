"""Triage Coordinator Orchestrator powered by Google ADK architecture."""

import re
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime

from nexus_ops.config import settings
from nexus_ops.tools.order_db_tool import lookup_order_details, update_order_status
from nexus_ops.tools.notification_tool import dispatch_customer_notification
from nexus_ops.core.specialist_agents import logistics_specialist, billing_specialist, compliance_specialist
from nexus_ops.core.guardrails import guardrails
from nexus_ops.core.state_machine import state_machine, CircuitBreakerError
from nexus_ops.core.constitutions import TRIAGE_COORDINATOR_CONSTITUTION
from nexus_ops.core.model_router import model_router
from nexus_ops.memory.session_manager import session_manager, MessageTurn
from nexus_ops.memory.tiered_memory import tiered_memory
from nexus_ops.memory.context_compactor import context_compactor
from nexus_ops.observability.otel_tracer import otel_tracer
from nexus_ops.observability.structured_logger import logger
from nexus_ops.observability.metrics import metrics


class TriageCoordinatorAgent:
    """Master Orchestrator coordinating enterprise support and operational dispute workflows."""

    def __init__(self, model_name: str = settings.frontier_model):
        self.name = "coordinator:triage_master"
        self.model_name = model_name
        self.constitution = TRIAGE_COORDINATOR_CONSTITUTION

    def process_request(
        self,
        user_prompt: str,
        session_id: Optional[str] = None,
        user_id: str = "CUST-001",
        authorization_token: str = "DELEGATED_USER_AUTH_TOKEN_VALID"
    ) -> Dict[str, Any]:
        """Main entry point for processing enterprise customer operations requests.

        Executes the 5-step operational loop:
        1. Perceive: Validate inputs, retrieve session & long-term customer context.
        2. Plan: Detect intent, identify order references, formulate execution trajectory.
        3. Act: Dispatch to bounded specialist agents and enterprise tools.
        4. Observe: Monitor tool responses, apply guardrails, prevent loops.
        5. Synthesize: Update persistent memory, dispatch notifications, return structured outcome.
        """
        metrics.record_request()
        run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
        session_id = session_id or f"SESS-{uuid.uuid4().hex[:8].upper()}"

        logger.info(f"[{run_id}] Starting TriageCoordinator for session {session_id}, user {user_id}")

        # Step 1: Perceive & Security Guardrail
        is_safe, security_error = guardrails.validate_user_input(user_prompt)
        if not is_safe:
            logger.log_intent_vs_outcome(
                planned_intent="SECURITY_SCAN",
                actual_outcome="SECURITY_REJECTED",
                intent_satisfied=False,
                discrepancy_reason=security_error,
                session_id=session_id,
                run_id=run_id
            )
            return {
                "run_id": run_id,
                "session_id": session_id,
                "user_id": user_id,
                "active_order_id": None,
                "status": "SECURITY_REJECTED",
                "final_response": security_error,
                "actions_taken": [],
                "escalated_to_hitl": False
            }

        # Step 2: Session & Tiered Context Setup
        session = session_manager.get_or_create_session(session_id, user_id)
        session.turns.append(MessageTurn(role="user", content=user_prompt))

        working_mem = tiered_memory.get_or_create_working_memory(run_id)
        customer_profile = tiered_memory.load_long_term_customer_profile(user_id)
        session.customer_tier = customer_profile.tier if customer_profile else "STANDARD"

        # Apply context compaction if turns exceed threshold
        compacted_history, was_compacted = context_compactor.compact_turns(session.turns)
        if was_compacted:
            logger.info(f"[{run_id}] Context compacted to mitigate Context Rot.")

        # Strategic Model Routing: Dynamically evaluate task complexity
        routing_decision = model_router.evaluate_complexity(
            user_prompt=user_prompt,
            customer_tier=session.customer_tier,
            turn_count=len(session.turns)
        )
        selected_model = routing_decision.selected_model
        logger.info(f"[{run_id}] Executing with dynamically routed model: {selected_model} ({routing_decision.tier})")

        # Step 3: Entity Extraction & Intent Classification
        order_match = re.search(r"ORD-[\w-]+", user_prompt, re.IGNORECASE)
        order_id = order_match.group(0).upper() if order_match else session.active_order_id or "ORD-901"
        session.active_order_id = order_id

        actions_taken: List[Dict[str, Any]] = []
        final_response_text = ""
        hitl_escalation = False

        try:
            with otel_tracer.trace_orchestration_step(session_id, user_id, working_mem.step_count, self.name):
                state_machine.validate_step(working_mem.step_count, run_id)
                working_mem.step_count += 1

                # Intent: Shipping / Logistics Tracking
                if any(w in user_prompt.lower() for w in ["track", "shipping", "where is", "delivered", "package", "delay"]):
                    working_mem.active_intent = "LOGISTICS_INQUIRY"
                    logistics_res = logistics_specialist.investigate(order_id)
                    actions_taken.append({"action": "logistics_investigation", "result": logistics_res})

                    if logistics_res.get("has_exception"):
                        # If delayed and customer asks for compensation or refund
                        if any(w in user_prompt.lower() for w in ["refund", "credit", "compensation", "late"]):
                            billing_res = billing_specialist.resolve_dispute(
                                order_id=order_id,
                                customer_id=user_id,
                                dispute_category="TRANSIT_DELAY",
                                requested_amount=50.0 if session.customer_tier == "ENTERPRISE" else 25.0,
                                authorization_token=authorization_token
                            )
                            actions_taken.append({"action": "dispute_resolution", "result": billing_res})
                            final_response_text = (
                                f"Order {order_id} was delayed due to carrier transit exception ({logistics_res.get('carrier')}). "
                                f"A carrier tracing ticket ({logistics_res.get('carrier_ticket', {}).get('ticket_id')}) was created. "
                                f"Under our {session.customer_tier} SLA policy, a courtesy credit of ${billing_res.get('authorized_amount', 0.0):.2f} "
                                f"has been authorized and refunded to your original payment method."
                            )
                        else:
                            final_response_text = (
                                f"Order {order_id} is currently in transit with {logistics_res.get('carrier')}. "
                                f"Status: {logistics_res.get('carrier_status')}. Carrier tracing ticket "
                                f"{logistics_res.get('carrier_ticket', {}).get('ticket_id')} has been opened to expedite delivery."
                            )
                    else:
                        final_response_text = (
                            f"Order {order_id} status is {logistics_res.get('carrier_status')}. "
                            f"Carrier: {logistics_res.get('carrier')}. Delivery date: {logistics_res.get('actual_delivery') or logistics_res.get('estimated_delivery')}."
                        )

                # Intent: Dispute / Refund / Cancellation
                elif any(w in user_prompt.lower() for w in ["refund", "damaged", "broken", "cancel", "dispute", "wrong"]):
                    working_mem.active_intent = "FINANCIAL_DISPUTE"
                    # Extract dollar amount if specified
                    amount_match = re.search(r"\$(\d+(\.\d+)?)", user_prompt)
                    req_amount = float(amount_match.group(1)) if amount_match else 75.0

                    # Check HITL guardrail
                    needs_hitl, hitl_reason = guardrails.evaluate_hitl_requirement(
                        action_name="REFUND",
                        amount_usd=req_amount,
                        customer_tier=session.customer_tier
                    )

                    if needs_hitl:
                        hitl_escalation = True
                        final_response_text = f"Your dispute for ${req_amount:.2f} requires Human-In-The-Loop approval. {hitl_reason}"
                        actions_taken.append({"action": "hitl_escalation", "reason": hitl_reason})
                        metrics.record_resolution(success=False, hitl=True)
                    else:
                        category = "DAMAGED_GOODS" if "damaged" in user_prompt.lower() else "BUYER_REMORSE"
                        billing_res = billing_specialist.resolve_dispute(
                            order_id=order_id,
                            customer_id=user_id,
                            dispute_category=category,
                            requested_amount=req_amount,
                            authorization_token=authorization_token
                        )
                        actions_taken.append({"action": "dispute_resolution", "result": billing_res})

                        if billing_res.get("status") == "EXECUTED":
                            final_response_text = (
                                f"Your refund dispute for Order {order_id} has been processed under {session.customer_tier} policy. "
                                f"Approved amount: ${billing_res.get('authorized_amount'):.2f}. "
                                f"Refund Reference: {billing_res.get('refund_details', {}).get('refund_id')}."
                            )
                        elif billing_res.get("status") == "ESCALATED_TO_HUMAN":
                            hitl_escalation = True
                            final_response_text = f"Dispute escalated to supervisor queue: {billing_res.get('message')}"
                        else:
                            final_response_text = f"Dispute resolution update: {billing_res.get('message')}"

                # General Order Lookup
                else:
                    working_mem.active_intent = "ORDER_LOOKUP"
                    order_info = lookup_order_details(order_id)
                    actions_taken.append({"action": "lookup_order", "result": order_info})
                    if order_info["found"]:
                        final_response_text = (
                            f"Order {order_id} is currently {order_info.get('status')}. "
                            f"Total: ${order_info.get('total_amount'):.2f} {order_info.get('currency')}. "
                            f"Tracking Number: {order_info.get('tracking_number') or 'Not yet assigned'}."
                        )
                    else:
                        final_response_text = order_info.get("error_message", "Order not found.")

        except CircuitBreakerError as e:
            logger.log_intent_vs_outcome(
                planned_intent=working_mem.active_intent or "OPERATIONAL_EXECUTION",
                actual_outcome="CIRCUIT_BREAKER_TRIPPED",
                intent_satisfied=False,
                discrepancy_reason=str(e),
                session_id=session_id,
                run_id=run_id
            )
            return {
                "run_id": run_id,
                "session_id": session_id,
                "status": "CIRCUIT_BREAKER_TRIPPED",
                "final_response": str(e),
                "actions_taken": actions_taken,
                "escalated_to_hitl": True
            }

        # Step 5: LLM Execution & Notification Synthesis
        llm_execution = model_router.generate_response(
            prompt=f"Task: Synthesize resolution for {user_id} on Order {order_id}.\nContext: {final_response_text}",
            system_instruction=self.constitution,
            decision=routing_decision
        )
        actions_taken.append({
            "action": "model_inference",
            "model": selected_model,
            "tier": routing_decision.tier,
            "status": "COMPLETED"
        })

        dispatch_customer_notification(
            customer_id=user_id,
            subject=f"Update regarding Order {order_id}",
            body=final_response_text,
            channel="EMAIL"
        )
        actions_taken.append({"action": "dispatch_notification", "customer_id": user_id})

        # Append assistant turn to session and save (automatically redacts PII before storage)
        session.turns.append(MessageTurn(role="assistant", content=final_response_text))
        session_manager.save_session(session)
        tiered_memory.clear_working_memory(run_id)

        metrics.record_resolution(success=True, hitl=hitl_escalation)

        # Explicit Intent vs Actual Outcome Telemetry Logging
        resolution_status = "COMPLETED" if not hitl_escalation else "ESCALATED_HITL"
        intent_satisfied = not hitl_escalation
        logger.log_intent_vs_outcome(
            planned_intent=working_mem.active_intent or "GENERAL_INQUIRY",
            actual_outcome=resolution_status,
            intent_satisfied=intent_satisfied,
            discrepancy_reason=None if intent_satisfied else "Resolution exceeded autonomous threshold, requiring HITL supervisor approval",
            session_id=session_id,
            run_id=run_id,
            selected_model=selected_model,
            complexity_score=routing_decision.complexity_score
        )

        return {
            "run_id": run_id,
            "session_id": session_id,
            "user_id": user_id,
            "active_order_id": order_id,
            "status": resolution_status,
            "selected_model": selected_model,
            "routing_decision": routing_decision.model_dump(),
            "final_response": final_response_text,
            "actions_taken": actions_taken,
            "escalated_to_hitl": hitl_escalation
        }


orchestrator = TriageCoordinatorAgent()

"""Tiered Memory System for Enterprise Agent Context Architecture."""

from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from nexus_ops.data.mock_db import db


class WorkingMemory(BaseModel):
    """Tier 1: Ephemeral scratchpad for an in-flight multi-step reasoning run."""
    run_id: str
    active_intent: Optional[str] = None
    extracted_entities: Dict[str, Any] = Field(default_factory=dict)
    intermediate_tool_outputs: List[Dict[str, Any]] = Field(default_factory=list)
    pending_actions: List[Dict[str, Any]] = Field(default_factory=list)
    step_count: int = 0


class CustomerLongTermProfile(BaseModel):
    """Tier 3: Long-term persistent customer memory and historical relationship."""
    customer_id: str
    name: str
    tier: str
    lifetime_spend: float
    dispute_count: int
    sla_response_hours: int
    relationship_notes: List[str] = Field(default_factory=list)
    last_interaction: Optional[str] = None


class TieredMemoryManager:
    """Orchestrates 3-tier memory: Working, Session, and Long-Term Persistent Memory."""

    def __init__(self):
        self._active_scratchpads: Dict[str, WorkingMemory] = {}

    def get_or_create_working_memory(self, run_id: str) -> WorkingMemory:
        """Accesses or initializes Tier 1 ephemeral scratchpad."""
        if run_id not in self._active_scratchpads:
            self._active_scratchpads[run_id] = WorkingMemory(run_id=run_id)
        return self._active_scratchpads[run_id]

    def clear_working_memory(self, run_id: str):
        """Flushes Tier 1 working memory after task completion."""
        self._active_scratchpads.pop(run_id, None)

    def load_long_term_customer_profile(self, customer_id: str) -> Optional[CustomerLongTermProfile]:
        """Loads Tier 3 persistent customer memory from CRM database."""
        cust = db.customers.get(customer_id.strip())
        if not cust:
            return None

        # Synthesize relationship notes from sentiment history
        notes = [f"Historical sentiment: {s}" for s in cust.sentiment_history]
        if cust.tier == "ENTERPRISE":
            notes.append("High-value enterprise contract: prioritize courtesy retention credits.")
        elif cust.tier == "VIP":
            notes.append("VIP loyalty member: expedited resolution track.")

        return CustomerLongTermProfile(
            customer_id=cust.customer_id,
            name=cust.name,
            tier=cust.tier,
            lifetime_spend=cust.lifetime_spend,
            dispute_count=cust.dispute_count,
            sla_response_hours=cust.sla_response_hours,
            relationship_notes=notes,
            last_interaction=datetime.utcnow().isoformat()
        )

    def record_interaction_outcome(self, customer_id: str, outcome_note: str):
        """Updates Tier 3 persistent customer memory with interaction outcome."""
        cust = db.customers.get(customer_id.strip())
        if cust:
            cust.sentiment_history.append(outcome_note)


tiered_memory = TieredMemoryManager()

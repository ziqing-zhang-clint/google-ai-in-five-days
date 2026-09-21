# AGENTS.md - Agent Fleet Architecture & Operational Governance

## System Overview: NexusOps Fleet
NexusOps is an enterprise multi-agent operations platform built with the Google Agent Development Kit (`google-adk`). It automates complex enterprise customer dispute resolutions, logistics carrier investigations, policy compliance checks, and financial remediations.

```
                           +---------------------------+
                           |   Customer / Channel UI   |
                           |    (FastAPI / Rich CLI)   |
                           +-------------+-------------+
                                         |
                                         v
                         +-------------------------------+
                         |      Security Guardrails      |
                         |  (Prompt Injection / Sanitizer|
                         +---------------+---------------+
                                         |
                                         v
                     +---------------------------------------+
                     |    Triage Coordinator Agent (ADK)     |
                     |  - Tiered Context & Compactor         |
                     |  - 5-Step Operational Loop            |
                     |  - Circuit Breaker Loop Guard         |
                     +---+---------------+---------------+---+
                         |               |               |
                         | (Delegation)  | (Delegation)  | (Delegation)
                         v               v               v
    +------------------------+ +-------------------+ +------------------------+
    |   LogisticsSpecialist  | | BillingSpecialist | | PolicyComplianceAgent  |
    +-----------+------------+ +---------+---------+ +-----------+------------+
                |                        |                       |
                v                        v                       v
    +------------------------+ +-------------------+ +------------------------+
    | CarrierLogisticsTool   | | PaymentGatewayTool| | EnterprisePolicyEngine |
    | OrderDatabaseTool      | | OrderDatabaseTool | | NotificationTool       |
    +------------------------+ +-------------------+ +------------------------+
```

---

## Agent Fleet Manifest

| Agent Identifier | Role | Bounded Context | Tools Accessible |
|---|---|---|---|
| `coordinator:triage_master` | Master Orchestrator | End-to-end customer triage, intent routing, multi-turn dialogue, HITL escalations | Delegated sub-agents, notification tool |
| `specialist:logistics` | Logistics Specialist | Carrier tracking, transit delay detection, investigation ticket dispatch | `track_carrier_shipment`, `open_carrier_investigation`, `lookup_order_details` |
| `specialist:billing` | Billing Specialist | Policy validation, ledger adjustments, refund executions | `evaluate_dispute_policy`, `execute_order_refund`, `lookup_payment_details`, `update_order_status` |
| `specialist:compliance` | Policy Compliance Agent | SLA verification, contract guarantees, compliance assertions | `evaluate_dispute_policy`, `lookup_order_details` |

---

## Memory & Context Hierarchy
1. **Tier 1 (Working Memory)**: Ephemeral scratchpad per execution `run_id`, recording intermediate entity states and loop counters. Flushed upon run completion.
2. **Tier 2 (Session Memory)**: Multi-turn SQLite persistence tracking conversation dialogue, active order references, and customer state.
3. **Tier 3 (Long-Term Memory)**: Persistent customer profile containing historical lifetime value (LTV), dispute counts, contract SLA tier, and sentiment history.
4. **Context Compaction**: Automated semantic compactor triggering when turns exceed threshold ($N \ge 8$), compressing intermediate turns while preserving the pinned initial request and active recency window.

---

## Operational Loop & Safety Protocols
Every agent executes the deterministic **5-Step Operational Loop**:
1. **Perceive**: Ingest prompt, run regex injection filter, retrieve session context and customer Tier.
2. **Plan**: Classify intent, bind order ID, calculate compensation boundaries.
3. **Act**: Invoke specialist sub-agents and execute authorized tool calls.
4. **Observe**: Verify tool response schemas, check circuit breaker step counter ($N \le 10$), detect repetitive tool loops.
5. **Synthesize**: Update customer sentiment history, dispatch customer notification, return structured result.

### Confused Deputy Defense
All write actions (financial refunds, order cancellation) require explicit contextual authorization tokens passed from the authenticated user context. Direct internal cross-tenant tool invocation without a validated token is strictly rejected.

"""Unit tests for Tiered Memory, Session Management, and Context Compaction."""

import pytest
import sqlite3
import tempfile
import os
from nexus_ops.memory.session_manager import SessionManager, SessionState, MessageTurn
from nexus_ops.memory.tiered_memory import TieredMemoryManager, WorkingMemory, CustomerLongTermProfile
from nexus_ops.memory.context_compactor import ContextCompactor
from nexus_ops.data.mock_db import db


@pytest.fixture
def temp_session_manager():
    """Provides a SessionManager with an isolated temporary SQLite database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_path = f.name
    mgr = SessionManager(db_path=temp_path)
    yield mgr
    if os.path.exists(temp_path):
        os.remove(temp_path)


def test_session_manager_create_and_retrieve(temp_session_manager):
    session = temp_session_manager.get_or_create_session("sess-101", "user-alice")
    assert session.session_id == "sess-101"
    assert session.user_id == "user-alice"
    assert len(session.turns) == 0

    # Modify state and save
    session.active_order_id = "ORD-2024-001"
    session.customer_tier = "ENTERPRISE"
    session.variables["dispute_category"] = "LOST_IN_TRANSIT"
    temp_session_manager.save_session(session)

    # Retrieve again and verify persistence
    reloaded = temp_session_manager.get_or_create_session("sess-101", "user-alice")
    assert reloaded.active_order_id == "ORD-2024-001"
    assert reloaded.customer_tier == "ENTERPRISE"
    assert reloaded.variables["dispute_category"] == "LOST_IN_TRANSIT"


def test_session_manager_append_turns(temp_session_manager):
    turn1 = temp_session_manager.append_turn(
        "sess-102", "user", "Where is my package?", {"channel": "web_chat"}
    )
    assert turn1.role == "user"
    assert turn1.content == "Where is my package?"
    assert turn1.metadata["channel"] == "web_chat"

    turn2 = temp_session_manager.append_turn(
        "sess-102", "assistant", "Let me check the tracking status for you."
    )
    assert turn2.role == "assistant"

    session = temp_session_manager.get_or_create_session("sess-102", "default_user")
    assert len(session.turns) == 2
    assert session.turns[0].content == "Where is my package?"
    assert session.turns[1].content == "Let me check the tracking status for you."


def test_tiered_memory_working_memory():
    mgr = TieredMemoryManager()
    run_id = "run-test-999"

    wm = mgr.get_or_create_working_memory(run_id)
    assert wm.run_id == run_id
    assert wm.step_count == 0

    wm.active_intent = "DISPUTE_INVESTIGATION"
    wm.extracted_entities["order_id"] = "ORD-2024-001"
    wm.step_count += 1

    # Access same run_id returns cached working memory
    wm2 = mgr.get_or_create_working_memory(run_id)
    assert wm2.active_intent == "DISPUTE_INVESTIGATION"
    assert wm2.step_count == 1

    # Clear working memory
    mgr.clear_working_memory(run_id)
    wm3 = mgr.get_or_create_working_memory(run_id)
    assert wm3.active_intent is None
    assert wm3.step_count == 0


def test_tiered_memory_customer_profile():
    mgr = TieredMemoryManager()

    # Load enterprise customer
    profile_ent = mgr.load_long_term_customer_profile("CUST-001")
    assert profile_ent is not None
    assert profile_ent.customer_id == "CUST-001"
    assert profile_ent.tier == "ENTERPRISE"
    assert any("courtesy retention credits" in note for note in profile_ent.relationship_notes)

    # Load VIP customer
    profile_vip = mgr.load_long_term_customer_profile("CUST-002")
    assert profile_vip is not None
    assert profile_vip.tier == "VIP"
    assert any("VIP loyalty member" in note for note in profile_vip.relationship_notes)

    # Load nonexistent customer
    assert mgr.load_long_term_customer_profile("CUST-NONEXISTENT") is None

    # Record interaction outcome
    initial_sentiments = list(db.customers["CUST-001"].sentiment_history)
    mgr.record_interaction_outcome("CUST-001", "Resolved transit delay with expedited replacement.")
    assert len(db.customers["CUST-001"].sentiment_history) == len(initial_sentiments) + 1
    assert "Resolved transit delay" in db.customers["CUST-001"].sentiment_history[-1]


def test_context_compactor_under_threshold():
    compactor = ContextCompactor(threshold=5)
    turns = [
        MessageTurn(role="user", content="Hello"),
        MessageTurn(role="assistant", content="Hi! How can I help?"),
        MessageTurn(role="user", content="I need help with an order.")
    ]
    payload, was_compacted = compactor.compact_turns(turns)
    assert was_compacted is False
    assert len(payload) == 3
    assert payload[0]["content"] == "Hello"
    assert payload[2]["content"] == "I need help with an order."


def test_context_compactor_above_threshold():
    compactor = ContextCompactor(threshold=4)
    turns = [
        MessageTurn(role="user", content="Root query: where is ORD-2024-001?"),
        MessageTurn(role="assistant", content="Checking logistics carrier database."),
        MessageTurn(role="tool", content="Carrier returned: Status In Transit, last scanned in Chicago."),
        MessageTurn(role="assistant", content="Logistics confirmed package is in transit."),
        MessageTurn(role="user", content="Is it delayed past SLA?"),
        MessageTurn(role="assistant", content="Consulting enterprise policy engine."),
        MessageTurn(role="user", content="Can I get a refund or reshipment?")
    ]

    payload, was_compacted = compactor.compact_turns(turns, max_active_window=2)
    assert was_compacted is True
    # Pinned root (turn 0) + 1 compacted summary + 2 recent turns = 4 total messages
    assert len(payload) == 4
    assert payload[0]["role"] == "user"
    assert "Root query" in payload[0]["content"]

    # Summary block in role system
    assert payload[1]["role"] == "system"
    assert "COMPACTED CONTEXT SUMMARY" in payload[1]["content"]
    assert "Tool result:" in payload[1]["content"]

    # Recent turns preserved
    assert payload[2]["role"] == "assistant"
    assert "Consulting enterprise policy engine." in payload[2]["content"]
    assert payload[3]["role"] == "user"
    assert "Can I get a refund or reshipment?" in payload[3]["content"]

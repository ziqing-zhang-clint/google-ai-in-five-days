"""Unit tests for enterprise tools and Pydantic validation."""

import pytest
from nexus_ops.tools.order_db_tool import lookup_order_details, update_order_status
from nexus_ops.tools.carrier_logistics_tool import track_carrier_shipment, open_carrier_investigation
from nexus_ops.tools.payment_gateway_tool import lookup_payment_details, execute_order_refund
from nexus_ops.tools.policy_engine_tool import evaluate_dispute_policy
from nexus_ops.tools.notification_tool import dispatch_customer_notification


def test_order_db_lookup_existing():
    res = lookup_order_details("ORD-901")
    assert res["found"] is True
    assert res["order_id"] == "ORD-901"
    assert res["total_amount"] == 189.50
    assert len(res["items"]) == 2


def test_order_db_lookup_missing():
    res = lookup_order_details("ORD-NON-EXISTENT")
    assert res["found"] is False
    assert "not found" in res["error_message"].lower()


def test_order_status_update():
    res = update_order_status("ORD-901", "DISPUTED", "Customer reported defect")
    assert res["success"] is True
    assert res["previous_status"] == "DELIVERED"
    assert res["current_status"] == "DISPUTED"


def test_order_status_update_invalid():
    res = update_order_status("ORD-901", "INVALID_STATE", "Invalid reason")
    assert res["success"] is False
    assert "invalid state" in res["error_message"].lower()


def test_carrier_logistics_tracking_delivered():
    res = track_carrier_shipment("TRK-FEDEX-901")
    assert res["found"] is True
    assert res["status"] == "DELIVERED"
    assert res["carrier"] == "FEDEX"
    assert res["has_transit_exception"] is False


def test_carrier_logistics_tracking_exception():
    res = track_carrier_shipment("TRK-UPS-902")
    assert res["found"] is True
    assert res["status"] == "EXCEPTION_DELAYED"
    assert res["has_transit_exception"] is True


def test_carrier_investigation_open():
    res = open_carrier_investigation("TRK-UPS-902", "WEATHER_DELAY", "EXPEDITED")
    assert res["status"] == "INVESTIGATION_OPEN"
    assert res["estimated_resolution_hours"] == 4
    assert res["ticket_id"].startswith("TKT-CARRIER-")


def test_payment_lookup():
    res = lookup_payment_details("TXN-STRIPE-901")
    assert res["found"] is True
    assert res["amount"] == 189.50
    assert res["status"] == "CAPTURED"


def test_refund_confused_deputy_token_protection():
    # Attempt refund without valid authorization token
    res = execute_order_refund("ORD-901", 50.0, "Customer request", authorization_token="")
    assert res["success"] is False
    assert res["status"] == "AUTH_REJECTED"


def test_refund_successful_execution():
    res = execute_order_refund(
        order_id="ORD-901",
        amount=75.0,
        reason="Defective part refund",
        authorization_token="DELEGATED_USER_AUTH_TOKEN_VALID"
    )
    assert res["success"] is True
    assert res["amount_refunded"] == 75.0
    assert res["status"] == "COMPLETED"


def test_refund_over_balance_rejected():
    res = execute_order_refund(
        order_id="ORD-901",
        amount=500.0,  # Exceeds total order amount of 189.50
        reason="Greedy refund",
        authorization_token="DELEGATED_USER_AUTH_TOKEN_VALID"
    )
    assert res["success"] is False
    assert res["status"] == "REJECTED_OVER_BALANCE"


def test_policy_engine_transit_delay():
    res = evaluate_dispute_policy(
        order_id="ORD-902",
        customer_id="CUST-002",
        dispute_category="TRANSIT_DELAY"
    )
    assert res["decision"] == "APPROVED"
    assert res["authorized_amount_usd"] == 25.0


def test_policy_engine_hitl_threshold():
    res = evaluate_dispute_policy(
        order_id="ORD-999",
        customer_id="CUST-001",
        dispute_category="DEFECTIVE",
        requested_compensation_usd=1250.0  # Exceeds HITL threshold of 250
    )
    assert res["decision"] == "REQUIRES_HITL_ESCALATION"
    assert res["authorized_amount_usd"] == 0.0


def test_notification_dispatch():
    res = dispatch_customer_notification(
        customer_id="CUST-001",
        subject="Your Refund Receipt",
        body="Refund of $75.00 has been sent."
    )
    assert res["delivered"] is True
    assert res["recipient_email"] == "jane.doe@acme.corp"
    assert res["notification_id"].startswith("NOTIF-")

"""Payment Gateway Tool for Stripe & ERP Financial Settlement."""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from nexus_ops.data.mock_db import db
from nexus_ops.config import settings


class PaymentLookupInput(BaseModel):
    transaction_id: str = Field(..., description="Unique transaction ID, e.g. 'TXN-STRIPE-901'.")


class PaymentLookupOutput(BaseModel):
    found: bool
    transaction_id: str
    order_id: Optional[str] = None
    amount: Optional[float] = None
    currency: str = "USD"
    status: Optional[str] = None
    payment_method: Optional[str] = None
    refunded_amount: float = 0.0
    error_message: Optional[str] = None


class RefundExecutionInput(BaseModel):
    order_id: str = Field(..., description="Order identifier to issue refund for.")
    amount: float = Field(..., gt=0.0, description="Dollar amount to refund. Must be > 0.")
    reason: str = Field(..., description="Justification for refund.")
    authorization_token: str = Field(
        ...,
        description="Delegated user/supervisor authorization JWT or cryptographic mandate token."
    )


class RefundExecutionOutput(BaseModel):
    success: bool
    refund_id: Optional[str] = None
    order_id: str
    amount_refunded: float
    remaining_balance: float
    status: str
    message: str


def lookup_payment_details(transaction_id: str) -> Dict[str, Any]:
    """Inspects payment gateway ledger for capture status and prior refund history.

    Preconditions: transaction_id must exist.
    Postconditions: Returns transaction amount, payment rail, and remaining refundable balance.
    """
    txn = db.payments.get(transaction_id.strip())
    if not txn:
        return PaymentLookupOutput(
            found=False,
            transaction_id=transaction_id,
            error_message=f"Transaction '{transaction_id}' not found in payment gateway."
        ).model_dump()

    return PaymentLookupOutput(
        found=True,
        transaction_id=txn.transaction_id,
        order_id=txn.order_id,
        amount=txn.amount,
        currency=txn.currency,
        status=txn.status,
        payment_method=txn.payment_method,
        refunded_amount=txn.refunded_amount
    ).model_dump()


def execute_order_refund(
    order_id: str,
    amount: float,
    reason: str,
    authorization_token: str
) -> Dict[str, Any]:
    """Issues a programmatic refund to customer's original payment method.

    Security & Confused Deputy Controls:
    1. Validates that authorization_token is non-empty and authorized.
    2. Validates refund amount against auto_refund_limit_usd threshold.
    3. Prevents cumulative refund from exceeding original captured amount.

    Preconditions: Order must exist; amount must be positive and within remaining transaction balance.
    Postconditions: Payment gateway executes refund; ledger updated; audit event published.
    """
    import uuid

    if not authorization_token or len(authorization_token.strip()) < 8:
        return RefundExecutionOutput(
            success=False,
            order_id=order_id,
            amount_refunded=0.0,
            remaining_balance=0.0,
            status="AUTH_REJECTED",
            message="Security Violation: Missing or invalid delegated authorization_token. Contextual AuthZ required."
        ).model_dump()

    order = db.orders.get(order_id.strip())
    if not order:
        return RefundExecutionOutput(
            success=False,
            order_id=order_id,
            amount_refunded=0.0,
            remaining_balance=0.0,
            status="FAILED",
            message=f"Order '{order_id}' does not exist."
        ).model_dump()

    txn = db.payments.get(order.payment_transaction_id)
    if not txn:
        return RefundExecutionOutput(
            success=False,
            order_id=order_id,
            amount_refunded=0.0,
            remaining_balance=0.0,
            status="FAILED",
            message=f"No payment transaction associated with order '{order_id}'."
        ).model_dump()

    # Calculate refundable headroom
    remaining = txn.amount - txn.refunded_amount
    if amount > remaining:
        return RefundExecutionOutput(
            success=False,
            order_id=order_id,
            amount_refunded=0.0,
            remaining_balance=remaining,
            status="REJECTED_OVER_BALANCE",
            message=f"Requested refund (${amount:.2f}) exceeds remaining balance (${remaining:.2f})."
        ).model_dump()

    # Enforce policy threshold
    if amount > settings.auto_refund_limit_usd and not authorization_token.startswith("SUPERVISOR_"):
        return RefundExecutionOutput(
            success=False,
            order_id=order_id,
            amount_refunded=0.0,
            remaining_balance=remaining,
            status="REQUIRES_SUPERVISOR_AUTH",
            message=f"Refund (${amount:.2f}) exceeds automated threshold (${settings.auto_refund_limit_usd:.2f}). Escalation required."
        ).model_dump()

    # Execute refund
    txn.refunded_amount += amount
    if txn.refunded_amount >= txn.amount:
        txn.status = "REFUNDED"
        order.status = "REFUNDED"
    else:
        txn.status = "PARTIALLY_REFUNDED"

    refund_id = f"REF-{uuid.uuid4().hex[:8].upper()}"
    order.notes.append(f"Refund {refund_id} for ${amount:.2f} executed. Reason: {reason}")

    db.audit_log.append({
        "timestamp": datetime.utcnow().isoformat(),
        "action": "REFUND_EXECUTION",
        "order_id": order_id,
        "transaction_id": txn.transaction_id,
        "refund_id": refund_id,
        "amount": amount,
        "reason": reason,
        "auth_token_preview": authorization_token[:10] + "..."
    })

    return RefundExecutionOutput(
        success=True,
        refund_id=refund_id,
        order_id=order_id,
        amount_refunded=amount,
        remaining_balance=txn.amount - txn.refunded_amount,
        status="COMPLETED",
        message=f"Successfully refunded ${amount:.2f} to original payment rail."
    ).model_dump()

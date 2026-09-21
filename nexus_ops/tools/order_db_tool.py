"""Order Database Tool for Enterprise ERP & Order Management."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from nexus_ops.data.mock_db import db


class OrderLookupInput(BaseModel):
    order_id: str = Field(
        ...,
        description="The unique enterprise order identifier, e.g. 'ORD-901', 'ORD-902'."
    )


class OrderLookupOutput(BaseModel):
    found: bool
    order_id: str
    customer_id: Optional[str] = None
    status: Optional[str] = None
    total_amount: Optional[float] = None
    currency: str = "USD"
    items: List[Dict[str, Any]] = Field(default_factory=list)
    tracking_number: Optional[str] = None
    order_date: Optional[str] = None
    notes: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None


class OrderStatusUpdateInput(BaseModel):
    order_id: str = Field(..., description="Target order identifier.")
    new_status: str = Field(
        ...,
        description="Target status state: 'PROCESSING', 'SHIPPED', 'DELIVERED', 'DISPUTED', 'REFUNDED', 'CANCELLED'."
    )
    reason: str = Field(..., description="Business rationale for the status update.")
    actor_id: str = Field(default="agent:nexus_ops", description="Principal identity triggering the change.")


class OrderStatusUpdateOutput(BaseModel):
    success: bool
    order_id: str
    previous_status: Optional[str] = None
    current_status: Optional[str] = None
    updated_at: str
    error_message: Optional[str] = None


def lookup_order_details(order_id: str) -> Dict[str, Any]:
    """Retrieves authoritative enterprise order details from ERP database.

    Preconditions: order_id must be provided in valid format (e.g., 'ORD-901').
    Postconditions: Returns itemized details, shipment tracking reference, and current lifecycle status.
    """
    order = db.orders.get(order_id.strip())
    if not order:
        return OrderLookupOutput(
            found=False,
            order_id=order_id,
            error_message=f"Order '{order_id}' not found in ERP database."
        ).model_dump()

    return OrderLookupOutput(
        found=True,
        order_id=order.order_id,
        customer_id=order.customer_id,
        status=order.status,
        total_amount=order.total_amount,
        currency=order.currency,
        items=[item.model_dump() for item in order.items],
        tracking_number=order.tracking_number,
        order_date=order.order_date,
        notes=order.notes
    ).model_dump()


def update_order_status(order_id: str, new_status: str, reason: str, actor_id: str = "agent:nexus_ops") -> Dict[str, Any]:
    """Updates the lifecycle status of an enterprise order in the ERP database.

    Preconditions: Order must exist; target status must be a valid state transition.
    Postconditions: Order status is persisted; event is logged in internal enterprise audit trail.
    """
    from datetime import datetime

    valid_states = {"PROCESSING", "SHIPPED", "DELIVERED", "DISPUTED", "REFUNDED", "CANCELLED"}
    new_status_upper = new_status.strip().upper()

    if new_status_upper not in valid_states:
        return OrderStatusUpdateOutput(
            success=False,
            order_id=order_id,
            updated_at=datetime.utcnow().isoformat(),
            error_message=f"Invalid state transition '{new_status}'. Allowed: {sorted(list(valid_states))}"
        ).model_dump()

    order = db.orders.get(order_id.strip())
    if not order:
        return OrderStatusUpdateOutput(
            success=False,
            order_id=order_id,
            updated_at=datetime.utcnow().isoformat(),
            error_message=f"Order '{order_id}' not found."
        ).model_dump()

    prev = order.status
    order.status = new_status_upper
    audit_note = f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}] Status changed from {prev} to {new_status_upper} by {actor_id}. Reason: {reason}"
    order.notes.append(audit_note)

    db.audit_log.append({
        "timestamp": datetime.utcnow().isoformat(),
        "action": "ORDER_STATUS_UPDATE",
        "order_id": order_id,
        "from": prev,
        "to": new_status_upper,
        "actor": actor_id,
        "reason": reason
    })

    return OrderStatusUpdateOutput(
        success=True,
        order_id=order_id,
        previous_status=prev,
        current_status=new_status_upper,
        updated_at=datetime.utcnow().isoformat()
    ).model_dump()

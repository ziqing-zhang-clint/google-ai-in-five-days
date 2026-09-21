"""Customer Communications & Omnichannel Notification Tool."""

from typing import Any, Dict
from pydantic import BaseModel, Field
from nexus_ops.data.mock_db import db


class NotificationInput(BaseModel):
    customer_id: str = Field(..., description="Target customer identifier.")
    subject: str = Field(..., description="Notification subject line.")
    body: str = Field(..., description="Communication message body.")
    channel: str = Field(default="EMAIL", description="Delivery channel: 'EMAIL', 'SMS', or 'SUPPORT_TICKET'.")


class NotificationOutput(BaseModel):
    delivered: bool
    notification_id: str
    recipient_email: str
    channel: str
    timestamp: str


def dispatch_customer_notification(
    customer_id: str,
    subject: str,
    body: str,
    channel: str = "EMAIL"
) -> Dict[str, Any]:
    """Dispatches resolution details and official status updates to customer contact channels.

    Preconditions: Customer must exist.
    Postconditions: Simulates email/SMS delivery; logs event to enterprise audit trail.
    """
    import uuid
    from datetime import datetime

    customer = db.customers.get(customer_id.strip())
    email = customer.email if customer else "unknown@customer.com"
    notif_id = f"NOTIF-{uuid.uuid4().hex[:8].upper()}"
    ts = datetime.utcnow().isoformat()

    db.audit_log.append({
        "timestamp": ts,
        "action": "CUSTOMER_NOTIFICATION_SENT",
        "customer_id": customer_id,
        "notification_id": notif_id,
        "channel": channel.upper(),
        "subject": subject
    })

    return NotificationOutput(
        delivered=True,
        notification_id=notif_id,
        recipient_email=email,
        channel=channel.upper(),
        timestamp=ts
    ).model_dump()

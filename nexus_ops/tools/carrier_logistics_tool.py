"""Logistics Carrier Tracking Tool for FedEx, UPS, and DHL Integration."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from nexus_ops.data.mock_db import db


class TrackingLookupInput(BaseModel):
    tracking_number: str = Field(
        ...,
        description="The carrier tracking reference, e.g. 'TRK-FEDEX-901', 'TRK-UPS-902'."
    )


class TrackingLookupOutput(BaseModel):
    found: bool
    tracking_number: str
    carrier: Optional[str] = None
    status: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    estimated_delivery: Optional[str] = None
    actual_delivery: Optional[str] = None
    events: List[Dict[str, str]] = Field(default_factory=list)
    has_transit_exception: bool = False
    error_message: Optional[str] = None


class CarrierInvestigationInput(BaseModel):
    tracking_number: str = Field(..., description="Target carrier tracking number.")
    issue_type: str = Field(
        ...,
        description="Classification of shipping issue: 'WEATHER_DELAY', 'LOST_IN_TRANSIT', 'DAMAGED_PACKAGE'."
    )
    priority: str = Field(default="STANDARD", description="'STANDARD' or 'EXPEDITED'.")


class CarrierInvestigationOutput(BaseModel):
    ticket_id: str
    tracking_number: str
    status: str
    estimated_resolution_hours: int
    confirmation_message: str


def track_carrier_shipment(tracking_number: str) -> Dict[str, Any]:
    """Retrieves real-time carrier telemetry and delivery status for a shipment.

    Preconditions: Valid carrier tracking number.
    Postconditions: Returns carrier route events, current delivery status, and exception indicators.
    """
    shipment = db.shipments.get(tracking_number.strip())
    if not shipment:
        return TrackingLookupOutput(
            found=False,
            tracking_number=tracking_number,
            error_message=f"Tracking number '{tracking_number}' not found with any integrated carrier."
        ).model_dump()

    is_exception = shipment.status in {"EXCEPTION_DELAYED", "LOST"}

    return TrackingLookupOutput(
        found=True,
        tracking_number=shipment.tracking_number,
        carrier=shipment.carrier,
        status=shipment.status,
        origin=shipment.origin,
        destination=shipment.destination,
        estimated_delivery=shipment.estimated_delivery,
        actual_delivery=shipment.actual_delivery,
        events=shipment.events,
        has_transit_exception=is_exception
    ).model_dump()


def open_carrier_investigation(tracking_number: str, issue_type: str, priority: str = "STANDARD") -> Dict[str, Any]:
    """Escalates an in-flight shipment issue directly to carrier dispatch operations.

    Preconditions: Tracking number exists and shipment is in an abnormal state.
    Postconditions: Creates carrier tracing inquiry ticket and returns tracking reference.
    """
    import uuid
    ticket_id = f"TKT-CARRIER-{uuid.uuid4().hex[:6].upper()}"

    res_hours = 4 if priority.upper() == "EXPEDITED" else 24

    return CarrierInvestigationOutput(
        ticket_id=ticket_id,
        tracking_number=tracking_number,
        status="INVESTIGATION_OPEN",
        estimated_resolution_hours=res_hours,
        confirmation_message=f"Carrier inquiry {ticket_id} opened for {tracking_number} ({issue_type}). ETA: {res_hours}h."
    ).model_dump()

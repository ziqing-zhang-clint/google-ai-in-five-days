"""Mock Enterprise Database for Orders, Logistics, Payments, and Policies."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class OrderItem(BaseModel):
    item_id: str
    name: str
    quantity: int
    unit_price: float


class Order(BaseModel):
    order_id: str
    customer_id: str
    order_date: str
    status: str  # PENDING, PROCESSING, SHIPPED, DELIVERED, DISPUTED, REFUNDED, CANCELLED
    total_amount: float
    currency: str = "USD"
    items: List[OrderItem]
    tracking_number: Optional[str] = None
    shipping_address: str
    payment_transaction_id: str
    notes: List[str] = Field(default_factory=list)


class ShipmentTracking(BaseModel):
    tracking_number: str
    carrier: str  # FEDEX, UPS, DHL
    status: str   # IN_TRANSIT, OUT_FOR_DELIVERY, DELIVERED, EXCEPTION_DELAYED, LOST
    origin: str
    destination: str
    estimated_delivery: str
    actual_delivery: Optional[str] = None
    events: List[Dict[str, str]]


class CustomerProfile(BaseModel):
    customer_id: str
    name: str
    email: str
    tier: str  # STANDARD, VIP, ENTERPRISE
    lifetime_spend: float
    dispute_count: int
    sla_response_hours: int
    sentiment_history: List[str] = Field(default_factory=list)


class PaymentTransaction(BaseModel):
    transaction_id: str
    order_id: str
    customer_id: str
    amount: float
    currency: str = "USD"
    status: str  # CAPTURED, REFUNDED, PARTIALLY_REFUNDED, DISPUTED
    payment_method: str
    refunded_amount: float = 0.0


class EnterpriseMockDB:
    """In-memory thread-safe mock database mimicking SAP ERP & Stripe."""

    def __init__(self):
        self.reset()

    def reset(self):
        now = datetime.utcnow()
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        three_days_ago = (now - timedelta(days=3)).strftime("%Y-%m-%d")
        last_week = (now - timedelta(days=7)).strftime("%Y-%m-%d")

        # Customers
        self.customers: Dict[str, CustomerProfile] = {
            "CUST-001": CustomerProfile(
                customer_id="CUST-001",
                name="Acme Corp (Jane Doe)",
                email="jane.doe@acme.corp",
                tier="ENTERPRISE",
                lifetime_spend=45800.0,
                dispute_count=0,
                sla_response_hours=2,
                sentiment_history=["SATISFIED", "VERY_SATISFIED"]
            ),
            "CUST-002": CustomerProfile(
                customer_id="CUST-002",
                name="Nexus Retail (Bob Smith)",
                email="bob.smith@nexusretail.com",
                tier="VIP",
                lifetime_spend=12400.0,
                dispute_count=1,
                sla_response_hours=4,
                sentiment_history=["NEUTRAL"]
            ),
            "CUST-003": CustomerProfile(
                customer_id="CUST-003",
                name="Alice Walker",
                email="alice.walker@gmail.com",
                tier="STANDARD",
                lifetime_spend=280.0,
                dispute_count=0,
                sla_response_hours=24,
                sentiment_history=["SATISFIED"]
            )
        }

        # Orders
        self.orders: Dict[str, Order] = {
            "ORD-901": Order(
                order_id="ORD-901",
                customer_id="CUST-001",
                order_date=three_days_ago,
                status="DELIVERED",
                total_amount=189.50,
                currency="USD",
                items=[
                    OrderItem(item_id="SKU-101", name="Ergonomic Desk Sensor Hub", quantity=2, unit_price=75.0),
                    OrderItem(item_id="SKU-102", name="USB-C Industrial Cable Pack", quantity=1, unit_price=39.50)
                ],
                tracking_number="TRK-FEDEX-901",
                shipping_address="100 Enterprise Way, Suite 400, Austin, TX",
                payment_transaction_id="TXN-STRIPE-901",
                notes=["Delivered to front desk"]
            ),
            "ORD-902": Order(
                order_id="ORD-902",
                customer_id="CUST-002",
                order_date=last_week,
                status="SHIPPED",
                total_amount=480.00,
                currency="USD",
                items=[
                    OrderItem(item_id="SKU-201", name="Enterprise Network Switch 8-Port", quantity=1, unit_price=480.00)
                ],
                tracking_number="TRK-UPS-902",
                shipping_address="500 Tech Blvd, San Jose, CA",
                payment_transaction_id="TXN-STRIPE-902",
                notes=["Delayed in transit due to severe weather exception"]
            ),
            "ORD-903": Order(
                order_id="ORD-903",
                customer_id="CUST-003",
                order_date=yesterday,
                status="PROCESSING",
                total_amount=45.00,
                currency="USD",
                items=[
                    OrderItem(item_id="SKU-301", name="Wireless Presentation Clicker", quantity=1, unit_price=45.00)
                ],
                tracking_number=None,
                shipping_address="12 Elm Street, Boston, MA",
                payment_transaction_id="TXN-STRIPE-903",
                notes=["Awaiting warehouse picking"]
            ),
            "ORD-999": Order(
                order_id="ORD-999",
                customer_id="CUST-001",
                order_date=last_week,
                status="DELIVERED",
                total_amount=1250.00,
                currency="USD",
                items=[
                    OrderItem(item_id="SKU-999", name="Industrial Edge Compute Server Node", quantity=1, unit_price=1250.00)
                ],
                tracking_number="TRK-DHL-999",
                shipping_address="100 Enterprise Way, Suite 400, Austin, TX",
                payment_transaction_id="TXN-STRIPE-999",
                notes=["High-value critical equipment"]
            )
        }

        # Shipments
        self.shipments: Dict[str, ShipmentTracking] = {
            "TRK-FEDEX-901": ShipmentTracking(
                tracking_number="TRK-FEDEX-901",
                carrier="FEDEX",
                status="DELIVERED",
                origin="Memphis, TN",
                destination="Austin, TX",
                estimated_delivery=three_days_ago,
                actual_delivery=three_days_ago,
                events=[
                    {"timestamp": three_days_ago + " 08:30", "location": "Austin, TX", "event": "Out for delivery"},
                    {"timestamp": three_days_ago + " 14:15", "location": "Austin, TX", "event": "Delivered to Reception"}
                ]
            ),
            "TRK-UPS-902": ShipmentTracking(
                tracking_number="TRK-UPS-902",
                carrier="UPS",
                status="EXCEPTION_DELAYED",
                origin="Louisville, KY",
                destination="San Jose, CA",
                estimated_delivery=three_days_ago,
                actual_delivery=None,
                events=[
                    {"timestamp": last_week + " 10:00", "location": "Louisville, KY", "event": "Departed Sorting Hub"},
                    {"timestamp": three_days_ago + " 19:40", "location": "Denver, CO", "event": "Severe Weather Disruption - Transit Delayed"}
                ]
            ),
            "TRK-DHL-999": ShipmentTracking(
                tracking_number="TRK-DHL-999",
                carrier="DHL",
                status="DELIVERED",
                origin="Cincinnati, OH",
                destination="Austin, TX",
                estimated_delivery=last_week,
                actual_delivery=last_week,
                events=[
                    {"timestamp": last_week + " 11:20", "location": "Austin, TX", "event": "Delivered - Signed by security"}
                ]
            )
        }

        # Payments
        self.payments: Dict[str, PaymentTransaction] = {
            "TXN-STRIPE-901": PaymentTransaction(
                transaction_id="TXN-STRIPE-901",
                order_id="ORD-901",
                customer_id="CUST-001",
                amount=189.50,
                status="CAPTURED",
                payment_method="Corporate Visa Ending 4092",
                refunded_amount=0.0
            ),
            "TXN-STRIPE-902": PaymentTransaction(
                transaction_id="TXN-STRIPE-902",
                order_id="ORD-902",
                customer_id="CUST-002",
                amount=480.00,
                status="CAPTURED",
                payment_method="Corporate Amex Ending 1004",
                refunded_amount=0.0
            ),
            "TXN-STRIPE-903": PaymentTransaction(
                transaction_id="TXN-STRIPE-903",
                order_id="ORD-903",
                customer_id="CUST-003",
                amount=45.00,
                status="CAPTURED",
                payment_method="Personal Mastercard Ending 8821",
                refunded_amount=0.0
            ),
            "TXN-STRIPE-999": PaymentTransaction(
                transaction_id="TXN-STRIPE-999",
                order_id="ORD-999",
                customer_id="CUST-001",
                amount=1250.00,
                status="CAPTURED",
                payment_method="Wire Transfer / Net-30",
                refunded_amount=0.0
            )
        }

        self.audit_log: List[Dict[str, Any]] = []


db = EnterpriseMockDB()

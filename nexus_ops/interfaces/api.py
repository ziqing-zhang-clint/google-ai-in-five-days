"""FastAPI REST Application for NexusOps Enterprise Operations Agent."""

import uvicorn
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from nexus_ops.config import settings
from nexus_ops.core.orchestrator import orchestrator
from nexus_ops.memory.session_manager import session_manager
from nexus_ops.tools.order_db_tool import lookup_order_details
from nexus_ops.observability.metrics import metrics
from nexus_ops.observability.structured_logger import logger

app = FastAPI(
    title="NexusOps Enterprise Agent API",
    description="Enterprise Operations & Dispute Intelligence Multi-Agent System built on Google ADK",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)


class ChatRequest(BaseModel):
    prompt: str = Field(..., json_schema_extra={"example": "Where is my order ORD-902? It seems delayed."})
    session_id: Optional[str] = Field(default=None, json_schema_extra={"example": "SESS-DEMO-001"})
    user_id: str = Field(default="CUST-001", json_schema_extra={"example": "CUST-001"})
    authorization_token: str = Field(
        default="DELEGATED_USER_AUTH_TOKEN_VALID",
        description="Contextual OAuth or delegation JWT token for Confused Deputy defense."
    )


class ChatResponse(BaseModel):
    run_id: str
    session_id: str
    user_id: Optional[str] = None
    active_order_id: Optional[str] = None
    status: str
    selected_model: Optional[str] = None
    routing_decision: Optional[Dict[str, Any]] = None
    final_response: str
    actions_taken: List[Dict[str, Any]]
    escalated_to_hitl: bool


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str
    version: str


@app.get("/healthz", response_model=HealthResponse, tags=["Health"])
def health_check():
    """Liveness and readiness probe for Kubernetes / Cloud Run."""
    return HealthResponse(
        status="HEALTHY",
        service="nexus-enterprise-ops-agent",
        environment=settings.environment,
        version="1.0.0"
    )


@app.post("/api/v1/chat", response_model=ChatResponse, tags=["Agent Operations"])
def process_chat(request: ChatRequest):
    """Submits a customer operational inquiry or dispute to the agent orchestrator."""
    logger.info(f"Incoming REST chat request from user {request.user_id}")
    result = orchestrator.process_request(
        user_prompt=request.prompt,
        session_id=request.session_id,
        user_id=request.user_id,
        authorization_token=request.authorization_token
    )
    return ChatResponse(**result)


@app.get("/api/v1/sessions/{session_id}", tags=["Sessions & Memory"])
async def get_session(session_id: str):
    """Retrieves conversation history and state variables for a session asynchronously."""
    session = await session_manager.get_or_create_session_async(session_id, user_id="anonymous")
    return session.model_dump()


@app.get("/api/v1/orders/{order_id}", tags=["ERP Orders"])
def get_order(order_id: str):
    """Direct ERP lookup for order details."""
    order = lookup_order_details(order_id)
    if not order["found"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=order["error_message"])
    return order


@app.get("/api/v1/metrics", tags=["Observability"])
def get_operational_metrics():
    """Returns runtime metrics, resolution rates, and tool counters."""
    return metrics.get_summary()


def start():
    """Launches the Uvicorn web server."""
    uvicorn.run(
        "nexus_ops.interfaces.api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=(settings.environment == "development")
    )


if __name__ == "__main__":
    start()

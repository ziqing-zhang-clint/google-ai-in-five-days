"""NexusOps Enterprise Operations & Dispute Intelligence Multi-Agent System."""

__version__ = "1.0.0"
__author__ = "Clint Zhang"

from nexus_ops.config import settings
from nexus_ops.core.orchestrator import orchestrator, TriageCoordinatorAgent

__all__ = ["settings", "orchestrator", "TriageCoordinatorAgent"]

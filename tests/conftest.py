"""Pytest Configuration and Fixtures."""

import pytest
from nexus_ops.data.mock_db import db
from nexus_ops.observability.metrics import metrics


@pytest.fixture(autouse=True)
def reset_database_and_metrics():
    """Ensures each test runs against a fresh, pristine mock database state."""
    db.reset()
    metrics.reset()
    yield
    db.reset()
    metrics.reset()

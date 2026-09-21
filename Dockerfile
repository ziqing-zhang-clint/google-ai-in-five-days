# ==============================================================================
# Multi-Stage Production Dockerfile for NexusOps Enterprise Operations Agent
# Compliant with Enterprise Container Security & Google Cloud Run Standards
# ==============================================================================

# Stage 1: Build Dependencies
FROM python:3.11-slim AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml ./
RUN pip install --user --no-warn-script-location -r requirements.txt

# Stage 2: Runtime Image
FROM python:3.11-slim AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/appuser/.local/bin:$PATH" \
    ENVIRONMENT="production" \
    API_HOST="0.0.0.0" \
    API_PORT=8000

# Install runtime curl for healthcheck probe
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Security: Create unprivileged system group and user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser

# Copy installed wheels and binaries from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application source code and evals
COPY --chown=appuser:appgroup nexus_ops/ /app/nexus_ops/
COPY --chown=appuser:appgroup evals/ /app/evals/
COPY --chown=appuser:appgroup pyproject.toml /app/pyproject.toml

# Set permissions for non-root user
RUN chown -R appuser:appgroup /app /home/appuser

USER appuser

# Expose API port (Cloud Run defaults to 8080 or PORT env)
EXPOSE 8000

# Container liveness / readiness health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

ENTRYPOINT ["uvicorn", "nexus_ops.interfaces.api:app", "--host", "0.0.0.0", "--port", "8000"]

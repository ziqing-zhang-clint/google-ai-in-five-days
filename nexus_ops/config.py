"""NexusOps Enterprise Agent Configuration Module."""

import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global configuration settings for NexusOps Enterprise Agent."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Gemini & Google Cloud Config
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    frontier_model: str = Field(default="gemini-2.5-pro", alias="NEXUS_FRONTIER_MODEL")
    fast_model: str = Field(default="gemini-2.5-flash", alias="NEXUS_FAST_MODEL")

    # Environment & Logging
    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Server Ports
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    # Persistence & Context
    database_url: str = Field(default="sqlite:///nexus_ops_sessions.db", alias="DATABASE_URL")
    max_session_history_steps: int = Field(default=10, alias="MAX_SESSION_HISTORY_STEPS")
    context_compaction_threshold: int = Field(default=8, alias="CONTEXT_COMPACTION_THRESHOLD")

    # OpenTelemetry & Observability
    otel_service_name: str = Field(default="nexus-enterprise-ops-agent", alias="OTEL_SERVICE_NAME")
    otel_exporter_otlp_endpoint: str = Field(default="http://localhost:4318", alias="OTEL_EXPORTER_OTLP_ENDPOINT")
    otel_traces_enabled: bool = Field(default=True, alias="OTEL_TRACES_ENABLED")

    # Guardrails & Circuit Breakers
    max_agent_iterations: int = Field(default=10, alias="MAX_AGENT_ITERATIONS")
    auto_refund_limit_usd: float = Field(default=100.0, alias="AUTO_REFUND_LIMIT_USD")
    hitl_mandatory_threshold_usd: float = Field(default=250.0, alias="HITL_MANDATORY_THRESHOLD_USD")

    def get_api_key(self) -> Optional[str]:
        """Resolve available Google Gemini API Key."""
        return self.gemini_api_key or self.google_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


settings = Settings()

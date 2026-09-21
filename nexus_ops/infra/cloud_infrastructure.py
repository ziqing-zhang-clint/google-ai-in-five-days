"""
NexusOps Cloud Infrastructure as Code (IaC) Specification & Provisioning Module.

Declaratively specifies and verifies cloud infrastructure resources for the NexusOps fleet:
- Google Cloud Run v2 Container Execution Service
- Least-Privilege IAM Service Accounts & Role Bindings
- Google Secret Manager API Key Vaults
- Google Cloud Trace & Logging Integrations
"""

from typing import Dict, Any
from pydantic import BaseModel, Field


class CloudRunResourceLimits(BaseModel):
    cpu: str = Field(default="2000m", description="CPU quota allocation for the agent runtime.")
    memory: str = Field(default="2Gi", description="Memory allocation for vector and LLM processing.")


class CloudRunScalingConfig(BaseModel):
    min_instance_count: int = Field(default=1, description="Minimum warm instances for sub-second latency.")
    max_instance_count: int = Field(default=10, description="Maximum scale-out ceiling under high load.")


class ServiceAccountConfig(BaseModel):
    account_id: str = Field(default="nexus-ops-agent-sa", description="IAM Service Account ID.")
    display_name: str = Field(default="NexusOps Multi-Agent Runtime Service Account")
    roles: list[str] = Field(
        default=[
            "roles/aiplatform.user",
            "roles/cloudtrace.agent",
            "roles/logging.logWriter",
            "roles/secretmanager.secretAccessor",
        ],
        description="Least-privilege IAM roles granted to the agent runtime.",
    )


class InfrastructureAsCodeConfig(BaseModel):
    """Declarative Infrastructure as Code (IaC) schema for Google Cloud deployment."""
    project_id: str = Field(default="nexus-ops-enterprise-prod")
    region: str = Field(default="us-central1")
    service_name: str = Field(default="nexus-enterprise-ops-agent")
    container_image: str = Field(default="gcr.io/nexus-ops-enterprise-prod/nexus-ops-agent:latest")
    service_account: ServiceAccountConfig = Field(default_factory=ServiceAccountConfig)
    resources: CloudRunResourceLimits = Field(default_factory=CloudRunResourceLimits)
    scaling: CloudRunScalingConfig = Field(default_factory=CloudRunScalingConfig)

    def to_terraform_hcl(self) -> str:
        """Renders the configuration as canonical Terraform HCL."""
        return f"""
# Auto-generated Terraform HCL from NexusOps IaC Specification
resource "google_cloud_run_v2_service" "{self.service_name}" {{
  name     = "{self.service_name}"
  location = "{self.region}"
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {{
    service_account = "{self.service_account.account_id}@{self.project_id}.iam.gserviceaccount.com"
    scaling {{
      min_instance_count = {self.scaling.min_instance_count}
      max_instance_count = {self.scaling.max_instance_count}
    }}
    containers {{
      image = "{self.container_image}"
      resources {{
        limits = {{
          cpu    = "{self.resources.cpu}"
          memory = "{self.resources.memory}"
        }}
      }}
    }}
  }}
}}
"""

    def to_dict(self) -> Dict[str, Any]:
        """Returns structured dictionary for cloud deployment managers."""
        return self.model_dump()


def get_production_iac_spec() -> InfrastructureAsCodeConfig:
    """Returns the validated production Infrastructure as Code configuration."""
    return InfrastructureAsCodeConfig()

# ==============================================================================
# Terraform Variables Specification for NexusOps Enterprise Deployment
# ==============================================================================

variable "project_id" {
  description = "The Google Cloud Project ID where NexusOps will be provisioned."
  type        = string
}

variable "region" {
  description = "The Google Cloud region for compute and data resources."
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Target deployment environment (development, staging, production)."
  type        = string
  default     = "production"
}

variable "container_image" {
  description = "Container image tag in Artifact Registry or Google Container Registry."
  type        = string
  default     = "gcr.io/google-ai-in-5-days/nexus-enterprise-ops-agent:latest"
}

variable "gemini_api_key" {
  description = "Google Gemini API key stored in Secret Manager."
  type        = string
  sensitive   = true
  default     = ""
}

variable "hitl_mandatory_threshold_usd" {
  description = "Financial threshold in USD that triggers mandatory Human-In-The-Loop escalation."
  type        = number
  default     = 250.0
}

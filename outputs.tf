# ==============================================================================
# Terraform Outputs Specification for NexusOps Enterprise Deployment
# ==============================================================================

output "cloud_run_service_url" {
  description = "The public URL of the deployed NexusOps Cloud Run service."
  value       = google_cloud_run_v2_service.nexus_service.uri
}

output "service_account_email" {
  description = "The runtime Service Account email managing least-privilege permissions."
  value       = google_service_account.nexus_agent_sa.email
}

output "secret_manager_secret_id" {
  description = "Google Secret Manager resource ID containing GEMINI_API_KEY."
  value       = google_secret_manager_secret.gemini_api_key_secret.id
}

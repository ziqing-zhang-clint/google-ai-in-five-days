# ==============================================================================
# Terraform Infrastructure as Code (IaC) for NexusOps Enterprise Operations Agent
# Provisions Google Cloud Run v2, Service Accounts, IAM, and Secret Manager
# ==============================================================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.20.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ------------------------------------------------------------------------------
# 1. Least-Privilege Service Account for Agent Runtime
# ------------------------------------------------------------------------------
resource "google_service_account" "nexus_agent_sa" {
  account_id   = "nexus-ops-agent-sa"
  display_name = "NexusOps Multi-Agent Runtime Service Account"
  description  = "Dedicated identity for NexusOps Cloud Run execution and tool operations"
}

# Grant Cloud Trace Agent for OpenTelemetry distributed tracing
resource "google_project_iam_member" "trace_agent" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.nexus_agent_sa.email}"
}

# Grant Cloud Logging Log Writer for structured JSON logs
resource "google_project_iam_member" "log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.nexus_agent_sa.email}"
}

# ------------------------------------------------------------------------------
# 2. Secret Manager for Secure Credential Management
# ------------------------------------------------------------------------------
resource "google_secret_manager_secret" "gemini_api_key_secret" {
  secret_id = "nexus-gemini-api-key"

  replication {
    auto {}
  }

  labels = {
    environment = var.environment
    app         = "nexus-enterprise-ops-agent"
  }
}

resource "google_secret_manager_secret_version" "gemini_api_key_version" {
  count       = var.gemini_api_key != "" ? 1 : 0
  secret      = google_secret_manager_secret.gemini_api_key_secret.id
  secret_data = var.gemini_api_key
}

# Grant runtime SA read access to the Gemini API Key secret
resource "google_secret_manager_secret_iam_member" "secret_accessor" {
  secret_id = google_secret_manager_secret.gemini_api_key_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.nexus_agent_sa.email}"
}

# ------------------------------------------------------------------------------
# 3. Google Cloud Run v2 Production Service
# ------------------------------------------------------------------------------
resource "google_cloud_run_v2_service" "nexus_service" {
  name     = "nexus-enterprise-ops-agent"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.nexus_agent_sa.email

    scaling {
      min_instance_count = 1
      max_instance_count = 10
    }

    containers {
      image = var.container_image

      resources {
        limits = {
          cpu    = "2000m"
          memory = "2Gi"
        }
      }

      ports {
        container_port = 8000
      }

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }

      env {
        name  = "LOG_LEVEL"
        value = "INFO"
      }

      env {
        name  = "NEXUS_FRONTIER_MODEL"
        value = "gemini-2.5-pro"
      }

      env {
        name  = "NEXUS_FAST_MODEL"
        value = "gemini-2.5-flash"
      }

      env {
        name  = "HITL_MANDATORY_THRESHOLD_USD"
        value = tostring(var.hitl_mandatory_threshold_usd)
      }

      env {
        name  = "OTEL_SERVICE_NAME"
        value = "nexus-enterprise-ops-agent"
      }

      env {
        name  = "OTEL_TRACES_ENABLED"
        value = "true"
      }

      env {
        name = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.gemini_api_key_secret.secret_id
            version = "latest"
          }
        }
      }

      startup_probe {
        http_get {
          path = "/healthz"
          port = 8000
        }
        initial_delay_seconds = 5
        period_seconds        = 10
        failure_threshold     = 3
      }

      liveness_probe {
        http_get {
          path = "/healthz"
          port = 8000
        }
        period_seconds    = 15
        failure_threshold = 3
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_secret_manager_secret_iam_member.secret_accessor
  ]
}

# ------------------------------------------------------------------------------
# 4. Ingress Access Policy
# ------------------------------------------------------------------------------
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  project  = google_cloud_run_v2_service.nexus_service.project
  location = google_cloud_run_v2_service.nexus_service.location
  name     = google_cloud_run_v2_service.nexus_service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

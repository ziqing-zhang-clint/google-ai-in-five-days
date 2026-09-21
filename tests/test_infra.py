"""
Tests for Infrastructure as Code (IaC) configuration and rendering.
"""

from nexus_ops.infra.cloud_infrastructure import (
    InfrastructureAsCodeConfig,
    get_production_iac_spec,
)


def test_iac_spec_defaults():
    spec = get_production_iac_spec()
    assert spec.service_name == "nexus-enterprise-ops-agent"
    assert spec.region == "us-central1"
    assert spec.resources.cpu == "2000m"
    assert spec.resources.memory == "2Gi"
    assert spec.scaling.min_instance_count == 1
    assert spec.scaling.max_instance_count == 10
    assert "roles/aiplatform.user" in spec.service_account.roles
    assert "roles/cloudtrace.agent" in spec.service_account.roles


def test_iac_terraform_hcl_rendering():
    spec = InfrastructureAsCodeConfig()
    hcl = spec.to_terraform_hcl()
    assert 'resource "google_cloud_run_v2_service"' in hcl
    assert "nexus-enterprise-ops-agent" in hcl
    assert "2000m" in hcl
    assert "2Gi" in hcl


def test_iac_dict_export():
    spec = InfrastructureAsCodeConfig()
    d = spec.to_dict()
    assert isinstance(d, dict)
    assert d["service_name"] == "nexus-enterprise-ops-agent"
    assert d["resources"]["memory"] == "2Gi"

"""Operator capability console tests.

Purpose: verify the browser-facing operator capability surface is read-only,
bounded, and backed by governed capability records.
Governance scope: operator web UI projection only.
Dependencies: gateway server and capability fabric defaults.
Invariants:
  - Operator capability views expose governed records, not raw fabric internals.
  - JSON and HTML surfaces are guarded by the authority operator boundary.
  - Filtering and pagination are deterministic.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.capability_fabric import (  # noqa: E402
    build_default_capability_admission_gate,
    build_software_dev_capability_admission_gate,
)
from gateway.operator_capability_console import build_operator_capability_read_model  # noqa: E402
from gateway.server import create_gateway_app  # noqa: E402


class StubPlatform:
    """Minimal platform fixture for gateway app construction."""

    def process_message(self, message, tenant_id: str, identity_id: str):  # noqa: ANN001
        return {
            "response": "ok",
            "tenant_id": tenant_id,
            "identity_id": identity_id,
        }


def _clock() -> str:
    return "2026-05-01T12:00:00+00:00"


def test_operator_capability_read_model_projects_governed_records_only() -> None:
    gate = build_default_capability_admission_gate(clock=_clock)

    read_model = build_operator_capability_read_model(
        capability_admission_gate=gate,
        domain="voice",
        risk_level="medium",
        audit_limit=2,
    )

    assert read_model["enabled"] is True
    assert read_model["capability_surface"] == "governed_capability_records"
    assert read_model["raw_tool_surface_exposed"] is False
    assert read_model["domain_filter"] == "voice"
    assert read_model["risk_level_filter"] == "medium"
    assert read_model["capability_count"] == 6
    assert read_model["domain_counts"] == {"voice": 6}
    assert read_model["maturity_counts"] == {"C3": 6}
    assert read_model["maturity_label_counts"] == {"Implemented": 6}
    assert read_model["production_ready_count"] == 0
    assert read_model["autonomy_ready_count"] == 0
    assert read_model["sandbox_required_count"] == 6
    assert read_model["admission_audit_page"]["limit"] == 2
    assert read_model["improvement_portfolio"]["href"] == "/runtime/self/capability-improvement-portfolio"
    assert read_model["improvement_portfolio"]["mutation_applied"] is False
    assert read_model["improvement_portfolio"]["activation_blocked"] is True
    assert all("extensions" not in item for item in read_model["capabilities"])
    assert all("input_schema_ref" not in item for item in read_model["capabilities"])
    assert all(item["maturity_level"] == "C3" for item in read_model["capabilities"])
    assert all(item["maturity_label"] == "Implemented" for item in read_model["capabilities"])
    assert read_model["friction_control"]["execution_authority_granted"] is False
    assert read_model["friction_control"]["default_boundary"] == "lab"
    assert read_model["friction_control"]["real_world_write_status"] == "blocked_until_production_witness"
    assert "L0" in read_model["unlock_level_counts"]
    assert set(read_model["operating_boundary_counts"]) == {"lab"}


def test_operator_capability_endpoint_reports_default_fabric() -> None:
    gate = build_default_capability_admission_gate(clock=_clock)
    app = create_gateway_app(
        platform=StubPlatform(),
        capability_admission_gate_override=gate,
    )
    client = TestClient(app)

    response = client.get("/operator/capabilities/read-model?domain=browser&audit_limit=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["domain_filter"] == "browser"
    assert payload["capability_count"] >= 1
    assert payload["raw_tool_surface_exposed"] is False
    assert payload["maturity_counts"]["C3"] >= 1
    assert payload["maturity_label_counts"]["Implemented"] >= 1
    assert payload["production_ready_count"] == 0
    assert payload["admission_audit_page"]["limit"] == 1
    assert payload["improvement_portfolio"]["schema_ref"] == "urn:mullusi:schema:capability-improvement-portfolio:1"
    assert payload["improvement_portfolio"]["operator_review_required"] is True
    assert all(item["domain"] == "browser" for item in payload["capabilities"])


def test_operator_console_links_capability_improvement_portfolio() -> None:
    gate = build_default_capability_admission_gate(clock=_clock)
    app = create_gateway_app(
        platform=StubPlatform(),
        capability_admission_gate_override=gate,
    )
    client = TestClient(app)

    response = client.get("/operator/capabilities?domain=voice")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Mullu Operator Capabilities" in response.text
    assert "Governed Capability Records" in response.text
    assert "voice.intent_confirm" in response.text
    assert "Maturity" in response.text
    assert "Label" in response.text
    assert "Implemented" in response.text
    assert "Production ready: 0" in response.text
    assert "Raw tools exposed: false" in response.text
    assert "Capability improvement portfolio" in response.text
    assert "/runtime/self/capability-improvement-portfolio" in response.text
    assert "Activation blocked: true" in response.text
    assert "Friction Control" in response.text
    assert "Fast lab ready" in response.text
    assert "friction read model" in response.text


def test_operator_capability_read_model_projects_friction_controls_for_software_dev() -> None:
    gate = build_software_dev_capability_admission_gate(clock=_clock)

    read_model = build_operator_capability_read_model(
        capability_admission_gate=gate,
        domain="software_dev",
    )
    capabilities = {item["capability_id"]: item for item in read_model["capabilities"]}
    workflow = read_model["friction_control"]["developer_workflow_v1"]

    assert read_model["capability_count"] == 6
    assert read_model["unlock_level_counts"]["L4"] == 1
    assert read_model["unlock_level_counts"]["L5"] == 1
    assert read_model["friction_control"]["fast_mode_lab_ready_count"] == 2
    assert workflow["workflow_id"] == "mullu_developer_workflow.v1"
    assert workflow["status"] == "preflight_ready"
    assert workflow["lab_mode_allowed"] is True
    assert workflow["real_world_effects_allowed"] is False
    assert workflow["approval_boundary"] == "before_pull_request_or_external_write"
    assert workflow["missing_capability_ids"] == []
    assert capabilities["software_dev.change.run"]["unlock_level"] == "L4"
    assert capabilities["software_dev.change.run"]["fast_mode_admission"] == "allowed_lab"
    assert capabilities["software_dev.change.run"]["friction_status"] == "approval_required"
    assert capabilities["software_dev.change.run"]["rollback_default"] is True
    assert capabilities["software_dev.pr_candidate.prepare"]["unlock_level"] == "L5"
    assert capabilities["software_dev.pr_candidate.prepare"]["next_unlock"] == "approval"
    assert "production_deployment_started" in capabilities["software_dev.change.run"]["blocked_actions"]
    assert "unapproved_execution" in capabilities["software_dev.pr_candidate.prepare"]["blocked_actions"]


def test_operator_friction_control_endpoint_projects_developer_workflow() -> None:
    gate = build_software_dev_capability_admission_gate(clock=_clock)
    app = create_gateway_app(
        platform=StubPlatform(),
        capability_admission_gate_override=gate,
    )
    client = TestClient(app)

    response = client.get("/operator/capabilities/friction-control/read-model?domain=software_dev")

    assert response.status_code == 200
    payload = response.json()
    workflow = payload["developer_workflow_v1"]
    assert payload["read_model_is_not_execution_authority"] is True
    assert payload["live_execution_enabled"] is False
    assert payload["source_refs"]["capability_surface"] == "governed_capability_records"
    assert payload["source_refs"]["domain_filter"] == "software_dev"
    assert payload["summary"]["capability_count"] == 6
    assert payload["summary"]["fast_mode_lab_ready_count"] == 2
    assert payload["summary"]["real_world_mode_allowed_count"] == 0
    assert workflow["workflow_id"] == "mullu_developer_workflow.v1"
    assert workflow["status"] == "preflight_ready"
    assert workflow["real_world_effects_allowed"] is False
    assert all("extensions" not in item for item in payload["capabilities"])
    assert all("allowed_tools" not in item for item in payload["capabilities"])


def test_operator_console_shows_developer_workflow_panel_for_software_dev() -> None:
    gate = build_software_dev_capability_admission_gate(clock=_clock)
    app = create_gateway_app(
        platform=StubPlatform(),
        capability_admission_gate_override=gate,
    )
    client = TestClient(app)

    response = client.get("/operator/capabilities?domain=software_dev")

    assert response.status_code == 200
    assert "Friction Control" in response.text
    assert "Workflow: preflight_ready" in response.text
    assert "Approval: before_pull_request_or_external_write" in response.text
    assert "/operator/capabilities/friction-control/read-model?domain=software_dev" in response.text
    assert "/operator/control-tower" in response.text


def test_operator_control_tower_projects_friction_control_capability_panel() -> None:
    gate = build_software_dev_capability_admission_gate(clock=_clock)
    app = create_gateway_app(
        platform=StubPlatform(),
        capability_admission_gate_override=gate,
    )
    client = TestClient(app)

    response = client.get("/operator/control-tower/read-model?domain=software_dev")

    assert response.status_code == 200
    payload = response.json()
    panels = {item["panel"]: item for item in payload["panels"]}
    capability_panel = panels["capability_health"]
    approval_panel = panels["approvals"]
    proof_panel = panels["proof_explorer"]
    workflow_panel = panels["workflow_monitor"]
    workflow = capability_panel["metadata"]["developer_workflow_v1"]
    summary = capability_panel["metadata"]["developer_workflow_summary"]
    assert payload["raw_tool_surface_exposed"] is False
    assert payload["overall_health"] == "missing"
    assert payload["missing_panel_count"] == payload["panel_count"] - 4
    assert capability_panel["source_surface"] == "capability_friction_control"
    assert capability_panel["item_count"] == 6
    assert capability_panel["blocked_count"] >= 1
    assert capability_panel["review_count"] >= 1
    assert approval_panel["source_surface"] == "operator_approval_history"
    assert approval_panel["metadata"]["approval_history_href"] == "/operator/approvals"
    assert proof_panel["source_surface"] == "operator_receipt_viewer"
    assert proof_panel["metadata"]["receipt_viewer_href"] == "/operator/receipts"
    assert workflow_panel["source_surface"] == "operator_workflow_monitor"
    assert workflow_panel["metadata"]["current_task_href"] == "/operator/current-task"
    assert workflow_panel["metadata"]["plan_review_href"] == "/operator/plan-review"
    assert workflow["workflow_id"] == "mullu_developer_workflow.v1"
    assert workflow["status"] == "preflight_ready"
    assert workflow["real_world_effects_allowed"] is False
    assert summary["task"] == "Mullu Developer Workflow v1"
    assert summary["risk"] == "low, local lab only"
    assert "raw_tool_surface" not in capability_panel["metadata"]


def test_operator_control_tower_html_shows_simple_developer_dashboard() -> None:
    gate = build_software_dev_capability_admission_gate(clock=_clock)
    app = create_gateway_app(
        platform=StubPlatform(),
        capability_admission_gate_override=gate,
    )
    client = TestClient(app)

    response = client.get("/operator/control-tower?domain=software_dev")

    assert response.status_code == 200
    assert "Mullu Operator Control Tower" in response.text
    assert "Developer Workflow" in response.text
    assert "Mullu Developer Workflow v1" in response.text
    assert "preflight_ready" in response.text
    assert "low, local lab only" in response.text
    assert "review diff receipt before approving pull request candidate" in response.text
    assert "/operator/capabilities/friction-control/read-model?domain=software_dev" in response.text
    assert "/operator/current-task" in response.text
    assert "/operator/plan-review" in response.text
    assert "/operator/approvals" in response.text
    assert "/operator/receipts" in response.text

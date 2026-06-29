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

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.capability_fabric import (  # noqa: E402
    build_default_capability_admission_gate,
    build_software_dev_capability_admission_gate,
)
from gateway.operator_capability_console import (  # noqa: E402
    build_developer_workflow_v1_run_read_model,
    build_operator_capability_read_model,
)
from gateway.operator_control_tower import (  # noqa: E402
    developer_workflow_capability_summary,
    developer_workflow_control_summary,
    developer_workflow_operator_action_banner,
    operator_dashboard_control_summary,
)
from gateway.operator_sandbox_patch_readiness import (  # noqa: E402
    SANDBOX_PATCH_READINESS_REGISTRY,
    sandbox_patch_readiness_compact_summary,
    sandbox_patch_readiness_receipt_entries,
    sandbox_patch_readiness_source_refs,
)
import gateway.server as server_module  # noqa: E402
from gateway.server import create_gateway_app  # noqa: E402
from scripts.build_developer_workflow_operator_receipt import canonical_hash as operator_receipt_hash  # noqa: E402
from mcoi_runtime.contracts.software_dev_loop import (  # noqa: E402
    SoftwareChangeReceipt,
    SoftwareChangeReceiptStage,
)
from mcoi_runtime.persistence.software_change_receipt_store import SoftwareChangeReceiptStore  # noqa: E402

WORKFLOW_RUN_SCHEMA_PATH = _ROOT / "schemas" / "workflow_run.schema.json"
SANDBOX_TO_PR_PACKET_SCHEMA_PATH = _ROOT / "schemas" / "sandbox_to_pr_preparation_packet.schema.json"
CONTROL_TOWER_STATUS_RECEIPT_SCHEMA_PATH = _ROOT / "schemas" / "operator_control_tower_status_receipt.schema.json"
SANDBOX_PATCH_READINESS_COMPACT_SCHEMA_PATH = (
    _ROOT / "schemas" / "operator_sandbox_patch_readiness_compact_read_model.schema.json"
)
DEVELOPER_WORKFLOW_STATUS_SCHEMA_PATH = (
    _ROOT / "schemas" / "operator_developer_workflow_status_read_model.schema.json"
)


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


def _sandbox_receipt_bundle() -> dict[str, object]:
    return {
        "bundle_id": "developer_workflow_sandbox_receipt_bundle.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": "developer_workflow_v1_collected_run",
        "bundle_status": "awaiting_receipts",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "rollback_default": True,
        "required_count": 4,
        "completed_count": 1,
        "receipts": [
            {
                "receipt_id": "sandbox_patch_receipt",
                "label": "Sandbox patch receipt",
                "status": "complete",
                "stage": "write_files_in_sandbox",
                "required": True,
                "source": "workflow_monitor.metadata.developer_workflow_run.receipt_checklist.sandbox_patch_receipt",
                "evidence_refs": ["proof://developer-workflow-v1/sandbox-patch/collected"],
                "before_state_hash": "sha256:before",
                "after_state_hash": "sha256:after",
                "diff_hash": "sha256:diff",
                "rollback_command": "git apply -R .change_assurance/sandbox_patch.diff",
                "command": "apply_patch",
            },
            {
                "receipt_id": "test_gate_receipt",
                "label": "Test gate receipt",
                "status": "pending",
                "stage": "run_tests",
                "required": True,
                "source": "workflow_monitor.metadata.developer_workflow_run.receipt_checklist.test_gate_receipt",
                "evidence_refs": [],
                "before_state_hash": "pending",
                "after_state_hash": "pending",
                "diff_hash": "pending",
                "rollback_command": "pending",
                "command": "pending",
            },
            {
                "receipt_id": "diff_review_receipt",
                "label": "Diff review receipt",
                "status": "pending",
                "stage": "show_diff",
                "required": True,
                "source": "workflow_monitor.metadata.developer_workflow_run.receipt_checklist.diff_review_receipt",
                "evidence_refs": [],
                "before_state_hash": "pending",
                "after_state_hash": "pending",
                "diff_hash": "pending",
                "rollback_command": "pending",
                "command": "pending",
            },
            {
                "receipt_id": "terminal_receipt",
                "label": "Terminal receipt",
                "status": "pending",
                "stage": "show_receipt",
                "required": True,
                "source": "workflow_monitor.metadata.developer_workflow_run.receipt_checklist.terminal_receipt",
                "evidence_refs": [],
                "before_state_hash": "pending",
                "after_state_hash": "pending",
                "diff_hash": "pending",
                "rollback_command": "pending",
                "command": "pending",
            },
        ],
    }


def _local_sandbox_proof_report() -> dict[str, object]:
    return {
        "ok": True,
        "errors": [],
        "evidence_path": ".change_assurance/developer_workflow_sandbox_receipt_evidence.collected.json",
        "bundle_path": ".change_assurance/developer_workflow_sandbox_receipt_bundle.collected.json",
        "attachment_packet_path": (
            ".change_assurance/developer_workflow_sandbox_receipt_attachment_packet.generated.json"
        ),
        "attachment_packet_status": "awaiting_attachments",
        "next_attachment_id": "test_gate_receipt",
        "bundle_status": "awaiting_receipts",
        "completed_count": 1,
        "required_count": 4,
        "pr_readiness_bundle_path": ".change_assurance/pr_readiness_bundle.generated.json",
        "operator_receipt_path": ".change_assurance/developer_workflow_operator_receipt.generated.json",
        "pr_readiness_status": "awaiting_sandbox_receipts",
        "ready_for_external_pr_execution": False,
        "command_preview_rendered": False,
        "execution_performed": False,
        "control_tower_url": "/operator/control-tower?domain=software_dev&include_local_sandbox_receipts=true",
        "workflow_read_model_url": (
            "/operator/developer-workflow/read-model?domain=software_dev&include_local_sandbox_receipts=true"
        ),
        "external_effects_allowed": False,
        "generated_artifacts": {
            "approval_packet": ".change_assurance/pr_preparation_approval_packet.generated.json",
            "command_preview": ".change_assurance/pr_command_preview_packet.generated.json",
            "external_approval_witness": ".change_assurance/external_pr_execution_approval_witness.generated.json",
            "local_candidate": ".change_assurance/local_pr_candidate_packet.generated.json",
            "metadata": ".change_assurance/pr_metadata_packet.generated.json",
            "operator_receipt": ".change_assurance/developer_workflow_operator_receipt.generated.json",
            "pr_readiness_bundle": ".change_assurance/pr_readiness_bundle.generated.json",
            "pr_tool_admission": ".change_assurance/pr_tool_admission_packet.generated.json",
            "sandbox_receipt_attachment_packet": (
                ".change_assurance/developer_workflow_sandbox_receipt_attachment_packet.generated.json"
            ),
            "sandbox_to_pr_packet": ".change_assurance/sandbox_to_pr_preparation_packet.generated.json",
        },
    }


def _local_rollback_summary_packet() -> dict[str, object]:
    return json.loads(
        (_ROOT / "examples" / "developer_workflow_local_rollback_summary_packet.foundation.json").read_text(
            encoding="utf-8"
        )
    )


def _local_rollback_approval_packet() -> dict[str, object]:
    return json.loads(
        (_ROOT / "examples" / "developer_workflow_local_rollback_approval_packet.foundation.json").read_text(
            encoding="utf-8"
        )
    )


def _local_rollback_execution_receipt() -> dict[str, object]:
    return json.loads(
        (_ROOT / "examples" / "developer_workflow_local_rollback_execution_receipt.foundation.json").read_text(
            encoding="utf-8"
        )
    )


def _developer_workflow_operator_receipt() -> dict[str, object]:
    receipt: dict[str, object] = {
        "receipt_id": "developer_workflow_operator_receipt.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": "developer_workflow_v1_foundation_run",
        "solver_outcome": "AwaitingEvidence",
        "execution_boundary": "local_lab_to_external_pr_preview",
        "execution_performed": False,
        "readiness_status": "awaiting_external_pr_approval",
        "sandbox_receipts": {
            "bundle_status": "receipts_complete",
            "completed_count": 4,
            "required_count": 4,
            "bundle_hash": "a" * 64,
        },
        "approvals": {
            "pr_preparation": {"status": "approved", "ready": True},
            "external_pr_execution": {"status": "pending", "ready": False},
        },
        "local_pr_candidate": {
            "candidate_status": "ready_for_pr_tool",
            "candidate_ready": True,
            "pr_tool_admitted": True,
        },
        "external_handoff": {
            "ready_for_external_pr_execution": False,
            "command_preview_rendered": False,
            "external_effects_allowed": False,
            "pr_creation_allowed": False,
            "branch_push_allowed": False,
        },
        "next_evidence": ["external_approval_witness", "command_preview"],
        "rollback": {
            "required": True,
            "evidence_refs": ["sandbox_patch_receipt"],
            "commands": [
                "git push origin --delete codex/developer-workflow-local-readiness",
                "gh pr close <pr-number> --comment 'Closing by governed rollback witness'",
            ],
        },
        "source_refs": {
            "sandbox_receipt_bundle_path": ".change_assurance/developer_workflow_sandbox_receipt_bundle.generated.json",
            "approval_packet_path": ".change_assurance/pr_preparation_approval_packet.approved.json",
            "local_candidate_packet_path": ".change_assurance/local_pr_candidate_packet.generated.json",
            "pr_tool_admission_packet_path": ".change_assurance/pr_tool_admission_packet.generated.json",
            "external_approval_witness_path": ".change_assurance/external_pr_execution_approval_witness.pending.json",
            "command_preview_packet_path": ".change_assurance/pr_command_preview_packet.blocked.json",
            "metadata_packet_path": ".change_assurance/pr_metadata_packet.generated.json",
            "pr_readiness_bundle_path": ".change_assurance/pr_readiness_bundle.generated.json",
            "receipt_builder": "python scripts/build_developer_workflow_operator_receipt.py",
        },
        "receipt_hash": "",
    }
    receipt["receipt_hash"] = operator_receipt_hash(receipt)
    return receipt


def _receipt(receipt_id: str, stage: SoftwareChangeReceiptStage) -> SoftwareChangeReceipt:
    return SoftwareChangeReceipt(
        receipt_id=receipt_id,
        request_id="software-request-1",
        stage=stage,
        cause="developer workflow test",
        outcome=stage.value,
        target_refs=("repo:test",),
        constraint_refs=("capability:software_dev.change.run",),
        evidence_refs=(f"evidence:{receipt_id}",),
        created_at=_clock(),
    )


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
    sandbox_to_pr = read_model["friction_control"]["sandbox_to_pr_now"]

    assert read_model["capability_count"] == 12
    assert read_model["unlock_level_counts"]["L4"] == 1
    assert read_model["unlock_level_counts"]["L5"] == 1
    assert read_model["friction_control"]["fast_mode_lab_ready_count"] == 2
    assert workflow["workflow_id"] == "mullu_developer_workflow.v1"
    assert workflow["status"] == "preflight_ready"
    assert workflow["lab_mode_allowed"] is True
    assert workflow["real_world_effects_allowed"] is False
    assert workflow["approval_boundary"] == "before_pull_request_or_external_write"
    assert workflow["missing_capability_ids"] == []
    assert sandbox_to_pr["status"] == "awaiting_sandbox_receipts"
    assert sandbox_to_pr["blocker"] == "sandbox_receipts_incomplete"
    assert sandbox_to_pr["policy_ready"] is True
    assert sandbox_to_pr["workflow_ready"] is True
    assert sandbox_to_pr["external_effects_allowed"] is False
    assert [item["label"] for item in sandbox_to_pr["next_evidence"]] == [
        "Sandbox patch receipt",
        "Test gate receipt",
        "Diff review receipt",
        "Terminal receipt",
    ]
    assert [stage["stage_id"] for stage in workflow["stages"]] == [
        "request_intake",
        "repo_map",
        "context_bundle",
        "gate_plan",
        "sandbox_change",
        "test_run",
        "diff_review",
        "receipt_review",
        "operator_approval",
        "pr_candidate",
    ]
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
    sandbox_to_pr = payload["sandbox_to_pr_now"]
    assert payload["read_model_is_not_execution_authority"] is True
    assert payload["live_execution_enabled"] is False
    assert payload["source_refs"]["capability_surface"] == "governed_capability_records"
    assert payload["source_refs"]["domain_filter"] == "software_dev"
    assert payload["summary"]["capability_count"] == 12
    assert payload["summary"]["fast_mode_lab_ready_count"] == 2
    assert payload["summary"]["real_world_mode_allowed_count"] == 0
    assert workflow["workflow_id"] == "mullu_developer_workflow.v1"
    assert workflow["status"] == "preflight_ready"
    assert workflow["real_world_effects_allowed"] is False
    assert sandbox_to_pr["status"] == "awaiting_sandbox_receipts"
    assert sandbox_to_pr["blocker"] == "sandbox_receipts_incomplete"
    assert sandbox_to_pr["next_action"] == "attach sandbox patch, test, diff, and terminal receipts"
    assert sandbox_to_pr["receipt_source"] == "operator_control_tower.workflow_monitor.sandbox_to_pr_packet"
    assert [item["evidence_id"] for item in sandbox_to_pr["next_evidence"]] == [
        "sandbox_patch_receipt",
        "test_gate_receipt",
        "diff_review_receipt",
        "terminal_receipt",
    ]
    assert all("extensions" not in item for item in payload["capabilities"])
    assert all("allowed_tools" not in item for item in payload["capabilities"])


def test_developer_workflow_run_read_model_conforms_to_workflow_schema() -> None:
    gate = build_software_dev_capability_admission_gate(clock=_clock)

    read_model = build_developer_workflow_v1_run_read_model(
        capability_admission_gate=gate,
        tenant_id="operator",
        domain="software_dev",
    )
    schema = json.loads(WORKFLOW_RUN_SCHEMA_PATH.read_text(encoding="utf-8"))

    Draft202012Validator(schema).validate(read_model)
    task_runs = {item["task_id"]: item for item in read_model["task_runs"]}
    assert read_model["workflow_id"] == "mullu_developer_workflow.v1"
    assert read_model["status"] == "waiting_for_approval"
    assert read_model["metadata"]["projection_only"] is True
    assert read_model["metadata"]["read_model_is_not_execution_authority"] is True
    assert read_model["metadata"]["execution_allowed"] is False
    assert read_model["metadata"]["real_world_effects_allowed"] is False
    assert task_runs["request_intake"]["status"] == "committed"
    assert task_runs["gate_plan"]["status"] == "committed"
    assert task_runs["sandbox_change"]["status"] == "created"
    assert task_runs["operator_approval"]["status"] == "waiting_for_approval"
    assert task_runs["pr_candidate"]["status"] == "created"
    assert read_model["run_hash"]


def test_developer_workflow_run_binds_software_receipts_to_stage_progress() -> None:
    gate = build_software_dev_capability_admission_gate(clock=_clock)
    store = SoftwareChangeReceiptStore()
    store.append(_receipt("software-receipt-patch", SoftwareChangeReceiptStage.PATCH_APPLIED))
    store.append(_receipt("software-receipt-gate", SoftwareChangeReceiptStage.GATE_EVALUATED))
    store.append(_receipt("software-receipt-terminal", SoftwareChangeReceiptStage.TERMINAL_CLOSED))

    read_model = build_developer_workflow_v1_run_read_model(
        capability_admission_gate=gate,
        software_receipt_store=store,
        tenant_id="operator",
        domain="software_dev",
    )
    task_runs = {item["task_id"]: item for item in read_model["task_runs"]}
    binding = read_model["metadata"]["software_receipt_binding"]

    assert task_runs["sandbox_change"]["status"] == "committed"
    assert task_runs["test_run"]["status"] == "committed"
    assert task_runs["diff_review"]["status"] == "committed"
    assert task_runs["receipt_review"]["status"] == "committed"
    assert task_runs["operator_approval"]["status"] == "waiting_for_approval"
    assert binding["enabled"] is True
    assert binding["total_receipts"] == 3
    assert binding["latest_stage"] == "terminal_closed"
    assert binding["stage_evidence"]["patch_applied"] == ["software-change-receipt:software-receipt-patch"]


def test_developer_workflow_run_binds_collected_sandbox_receipt_bundle() -> None:
    gate = build_software_dev_capability_admission_gate(clock=_clock)

    read_model = build_developer_workflow_v1_run_read_model(
        capability_admission_gate=gate,
        sandbox_receipt_bundle=_sandbox_receipt_bundle(),
        tenant_id="operator",
        domain="software_dev",
    )
    task_runs = {item["task_id"]: item for item in read_model["task_runs"]}
    binding = read_model["metadata"]["software_receipt_binding"]

    assert binding["enabled"] is True
    assert binding["binding_status"] == "bundle_bound"
    assert binding["total_receipts"] == 1
    assert binding["sandbox_receipt_bundle_status"] == "awaiting_receipts"
    assert binding["sandbox_receipt_bundle_completed_count"] == 1
    assert binding["stage_evidence"]["sandbox_patch_receipt"] == [
        "proof://developer-workflow-v1/sandbox-patch/collected"
    ]
    assert task_runs["sandbox_change"]["status"] == "committed"
    assert task_runs["test_run"]["status"] == "created"
    assert task_runs["diff_review"]["status"] == "created"
    assert task_runs["receipt_review"]["status"] == "created"


def test_developer_workflow_endpoint_exposes_run_receipt_and_html() -> None:
    gate = build_software_dev_capability_admission_gate(clock=_clock)
    store = SoftwareChangeReceiptStore()
    store.append(_receipt("software-receipt-patch", SoftwareChangeReceiptStage.PATCH_APPLIED))
    app = create_gateway_app(
        platform=StubPlatform(),
        capability_admission_gate_override=gate,
        software_receipt_store_override=store,
    )
    client = TestClient(app)

    json_response = client.get("/operator/developer-workflow/read-model?domain=software_dev")
    html_response = client.get("/operator/developer-workflow?domain=software_dev")

    assert json_response.status_code == 200
    assert html_response.status_code == 200
    payload = json_response.json()
    task_runs = {item["task_id"]: item for item in payload["task_runs"]}
    assert payload["workflow_run_id"] == "workflow-run-mullu-developer-workflow-v1-foundation"
    assert payload["status"] == "waiting_for_approval"
    assert payload["metadata"]["write_allowed"] is False
    assert payload["metadata"]["software_receipt_binding"]["total_receipts"] == 1
    assert task_runs["sandbox_change"]["status"] == "committed"
    assert "Mullu Developer Workflow v1" in html_response.text
    assert "operator_approval" in html_response.text
    assert "Receipt binding: bound" in html_response.text
    assert "/operator/developer-workflow/read-model" in html_response.text


def test_developer_workflow_endpoint_can_opt_into_local_sandbox_receipt_bundle(
    monkeypatch,
    tmp_path: Path,
) -> None:
    bundle_path = tmp_path / "developer_workflow_sandbox_receipt_bundle.collected.json"
    bundle_path.write_text(json.dumps(_sandbox_receipt_bundle(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    monkeypatch.setattr(server_module, "LOCAL_SANDBOX_RECEIPT_BUNDLE_PATH", bundle_path)
    gate = build_software_dev_capability_admission_gate(clock=_clock)
    app = create_gateway_app(
        platform=StubPlatform(),
        capability_admission_gate_override=gate,
    )
    client = TestClient(app)

    response = client.get(
        "/operator/developer-workflow/read-model"
        "?domain=software_dev&include_local_sandbox_receipts=true"
    )

    assert response.status_code == 200
    payload = response.json()
    task_runs = {item["task_id"]: item for item in payload["task_runs"]}
    binding = payload["metadata"]["software_receipt_binding"]
    assert binding["binding_status"] == "bound"
    assert binding["sandbox_receipt_bundle_completed_count"] == 1
    assert binding["stage_evidence"]["sandbox_patch_receipt"] == [
        "proof://developer-workflow-v1/sandbox-patch/collected"
    ]
    assert task_runs["sandbox_change"]["status"] == "committed"
    assert task_runs["test_run"]["status"] == "created"
    assert payload["metadata"]["execution_allowed"] is False


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
    assert "PR blocker: sandbox_receipts_incomplete" in response.text
    assert "PR status: awaiting_sandbox_receipts" in response.text
    assert "PR next: attach sandbox patch, test, diff, and terminal receipts" in response.text
    assert "Next evidence" in response.text
    assert "Sandbox patch receipt" in response.text
    assert "Test gate receipt" in response.text
    assert "Diff review receipt" in response.text
    assert "Terminal receipt" in response.text
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
    rollback = capability_panel["metadata"]["rollback_summary"]
    unlock_queue = capability_panel["metadata"]["next_unlock_queue"]
    passports = capability_panel["metadata"]["capability_passports"]
    mode_selector = capability_panel["metadata"]["mode_selector"]
    sandbox_to_pr_policy = capability_panel["metadata"]["sandbox_to_pr_policy"]
    assert payload["raw_tool_surface_exposed"] is False
    assert payload["overall_health"] == "missing"
    assert payload["missing_panel_count"] == payload["panel_count"] - 4
    assert capability_panel["source_surface"] == "capability_friction_control"
    assert capability_panel["item_count"] == 12
    assert capability_panel["blocked_count"] >= 1
    assert capability_panel["review_count"] >= 1
    assert capability_panel["metadata"]["safe_automatic_zone_count"] == 7
    safe_action_candidates = capability_panel["metadata"]["safe_automatic_action_candidates"]
    assert len(safe_action_candidates) == 7
    docs_candidate = next(item for item in safe_action_candidates if item["zone"] == "write_docs")
    assert docs_candidate["candidate_id"] == "safe_zone.write_docs"
    assert docs_candidate["title"] == "Prepare documentation update"
    assert docs_candidate["status"] == "candidate"
    assert docs_candidate["primary_action"] == "Prepare documentation update in local sandbox"
    assert docs_candidate["primary_href"] == "/operator/control-tower?domain=software_dev"
    assert docs_candidate["risk"] == "low, local lab only"
    assert docs_candidate["execution_boundary"] == "local_lab_only"
    assert docs_candidate["approval_required"] is False
    assert docs_candidate["external_effects_allowed"] is False
    assert capability_panel["metadata"]["dangerous_zone_count"] == 7
    dangerous_zone_blockers = capability_panel["metadata"]["dangerous_zone_blockers"]
    assert len(dangerous_zone_blockers) == 7
    deploy_blocker = next(item for item in dangerous_zone_blockers if item["zone"] == "deploy")
    assert deploy_blocker["blocker_id"] == "dangerous_zone.deploy"
    assert deploy_blocker["title"] == "Deploy"
    assert deploy_blocker["status"] == "blocked"
    assert deploy_blocker["reason"] == "dangerous_zone_requires_explicit_approval"
    assert deploy_blocker["required_evidence"] == [
        "operator_approval",
        "rollback_plan",
        "effect_receipt",
    ]
    assert deploy_blocker["risk"] == "high, real-world boundary"
    assert deploy_blocker["execution_boundary"] == "real_world"
    assert deploy_blocker["approval_required"] is True
    assert deploy_blocker["external_effects_allowed"] is False
    lab_real_world = capability_panel["metadata"]["lab_real_world_summary"]
    assert lab_real_world["summary_id"] == "lab_real_world.foundation"
    assert lab_real_world["lab_mode_allowed"] is True
    assert lab_real_world["lab_safe_candidate_count"] == len(safe_action_candidates)
    assert lab_real_world["fast_mode_lab_ready_count"] == capability_panel["metadata"]["fast_mode_lab_ready_count"]
    assert lab_real_world["real_world_effects_allowed"] is False
    assert lab_real_world["real_world_write_status"] == capability_panel["metadata"]["real_world_write_status"]
    assert lab_real_world["dangerous_blocker_count"] == len(dangerous_zone_blockers)
    assert lab_real_world["dangerous_approval_required_count"] == 7
    assert "Lab mode can prepare 7 local candidates" in lab_real_world["operator_message"]
    assert lab_real_world["lab_execution_boundary"] == "local_lab_only"
    assert lab_real_world["real_world_execution_boundary"] == "real_world"
    assert lab_real_world["external_effects_allowed"] is False
    assert lab_real_world["control_summary"] == {
        "contract_id": "operator_dashboard_control_summary.v1",
        "summary_id": "lab_real_world.control_summary.v1",
        "operator_message": lab_real_world["operator_message"],
        "action_banner": lab_real_world["operator_message"],
        "capability_id": "lab_real_world.boundary",
        "mode": "lab",
        "current_level": "L3",
        "next_level": "L9",
        "status": "blocked",
        "blocked_reason": "real_world_effect_boundary",
        "next_unlock": "approval",
        "next_evidence_count": lab_real_world["dangerous_approval_required_count"],
        "external_effects_allowed": False,
        "rollback_required": True,
    }
    approval_boundary = capability_panel["metadata"]["approval_boundary_summary"]
    assert approval_boundary["summary_id"] == "approval_boundary.foundation"
    assert approval_boundary["local_auto_candidate_count"] == len(safe_action_candidates)
    assert approval_boundary["approval_unlock_count"] >= 1
    assert approval_boundary["dangerous_approval_required_count"] == 7
    assert approval_boundary["pr_approval_required"] is True
    assert approval_boundary["approval_boundary"] == "before_pr_or_real_world_effect"
    assert approval_boundary["next_approval_capability_id"]
    assert "local automatic candidates" in approval_boundary["operator_message"]
    assert approval_boundary["execution_boundary"] == "local_lab_only"
    assert approval_boundary["external_effects_allowed"] is False
    assert approval_boundary["control_summary"] == {
        "contract_id": "operator_dashboard_control_summary.v1",
        "summary_id": "approval_boundary.control_summary.v1",
        "operator_message": approval_boundary["operator_message"],
        "action_banner": approval_boundary["operator_message"],
        "capability_id": approval_boundary["next_approval_capability_id"],
        "mode": "lab",
        "current_level": "L3",
        "next_level": "L5",
        "status": "approval_required",
        "blocked_reason": "before_pr_or_real_world_effect",
        "next_unlock": "approval",
        "next_evidence_count": approval_boundary["approval_unlock_count"],
        "external_effects_allowed": False,
        "rollback_required": True,
    }
    rollback_control = capability_panel["metadata"]["rollback_control_summary"]
    assert rollback_control["summary_id"] == "rollback_control.foundation"
    assert rollback_control["rollback_default_count"] == rollback["rollback_default_count"]
    assert rollback_control["rollback_required_count"] == rollback["rollback_required_count"]
    assert rollback_control["capability_count"] == capability_panel["item_count"]
    assert rollback_control["rollback_default_ready"] is True
    assert rollback_control["sandbox_to_pr_policy_ready"] is True
    assert rollback_control["rollback_policy"] == rollback["rollback_policy"]
    assert rollback_control["rollback_receipt_source"] == rollback["rollback_receipt_source"]
    assert "rollback execution remains receipt-bound" in rollback_control["operator_message"]
    assert rollback_control["execution_boundary"] == "local_lab_only"
    assert rollback_control["external_effects_allowed"] is False
    registry_summary = capability_panel["metadata"]["capability_registry_summary"]
    assert registry_summary["summary_id"] == "capability_registry.foundation"
    assert registry_summary["capability_count"] == 12
    assert registry_summary["blocked_count"] == capability_panel["blocked_count"]
    assert registry_summary["approval_required_count"] == capability_panel["review_count"]
    assert registry_summary["pending_unlock_count"] == len(unlock_queue)
    assert registry_summary["next_blocked_capability_id"] == unlock_queue[0]["capability_id"]
    assert registry_summary["next_blocked_reason"] == unlock_queue[0]["next_unlock"]
    assert registry_summary["next_required_evidence"] == unlock_queue[0]["required_evidence"]
    assert registry_summary["next_required_evidence_count"] == len(unlock_queue[0]["required_evidence"])
    assert "capabilities preflight-ready" in registry_summary["operator_message"]
    assert registry_summary["execution_boundary"] == "local_lab_only"
    assert registry_summary["external_effects_allowed"] is False
    assert registry_summary["control_summary"] == {
        "contract_id": "operator_dashboard_control_summary.v1",
        "summary_id": "capability_registry.control_summary.v1",
        "operator_message": registry_summary["operator_message"],
        "action_banner": registry_summary["operator_message"],
        "capability_id": registry_summary["next_blocked_capability_id"],
        "mode": "lab",
        "current_level": "L0",
        "next_level": "L3",
        "status": "approval_required",
        "blocked_reason": registry_summary["next_blocked_reason"],
        "next_unlock": registry_summary["next_blocked_reason"],
        "next_evidence_count": registry_summary["next_required_evidence_count"],
        "external_effects_allowed": False,
        "rollback_required": True,
    }
    safe_vs_dangerous = capability_panel["metadata"]["safe_vs_dangerous_summary"]
    assert safe_vs_dangerous["summary_id"] == "safe_vs_dangerous.local_lab"
    assert safe_vs_dangerous["safe_candidate_count"] == 7
    assert safe_vs_dangerous["dangerous_blocker_count"] == 7
    assert safe_vs_dangerous["first_safe_zone"] == "write_docs"
    assert safe_vs_dangerous["first_safe_action"] == "Prepare documentation update in local sandbox"
    assert safe_vs_dangerous["first_dangerous_zone"] == "delete_files"
    assert safe_vs_dangerous["first_dangerous_reason"] == "dangerous_zone_requires_explicit_approval"
    assert safe_vs_dangerous["operator_message"] == (
        "7 local-lab candidates available; 7 real-world zones blocked pending explicit approval"
    )
    assert safe_vs_dangerous["safe_execution_boundary"] == "local_lab_only"
    assert safe_vs_dangerous["dangerous_execution_boundary"] == "real_world"
    assert safe_vs_dangerous["external_effects_allowed"] is False
    assert safe_vs_dangerous["control_summary"] == {
        "contract_id": "operator_dashboard_control_summary.v1",
        "summary_id": "safe_vs_dangerous.control_summary.v1",
        "operator_message": safe_vs_dangerous["operator_message"],
        "action_banner": safe_vs_dangerous["operator_message"],
        "capability_id": "safe_vs_dangerous.boundary",
        "mode": "lab",
        "current_level": "L3",
        "next_level": "L9",
        "status": "blocked",
        "blocked_reason": safe_vs_dangerous["first_dangerous_reason"],
        "next_unlock": "approval",
        "next_evidence_count": safe_vs_dangerous["dangerous_blocker_count"],
        "external_effects_allowed": False,
        "rollback_required": True,
    }
    unlock_readiness = capability_panel["metadata"]["unlock_readiness_summary"]
    assert unlock_readiness["summary_id"] == "unlock_readiness.local_lab"
    assert unlock_readiness["pending_unlock_count"] == len(unlock_queue)
    assert unlock_readiness["safe_candidate_count"] == 7
    assert unlock_readiness["dangerous_blocker_count"] == 7
    assert unlock_readiness["next_capability_id"] == unlock_queue[0]["capability_id"]
    assert unlock_readiness["next_unlock"] == unlock_queue[0]["next_unlock"]
    assert unlock_readiness["next_required_evidence"] == unlock_queue[0]["required_evidence"]
    assert unlock_readiness["next_required_evidence_count"] == len(unlock_queue[0]["required_evidence"])
    assert unlock_readiness["safe_candidates_ready"] == 7
    assert unlock_readiness["dangerous_blockers_requiring_approval"] == 7
    assert "pending unlocks; next evidence" in unlock_readiness["operator_message"]
    assert unlock_readiness["execution_boundary"] == "local_lab_only"
    assert unlock_readiness["external_effects_allowed"] is False
    assert unlock_readiness["control_summary"] == {
        "contract_id": "operator_dashboard_control_summary.v1",
        "summary_id": "unlock_readiness.control_summary.v1",
        "operator_message": unlock_readiness["operator_message"],
        "action_banner": unlock_readiness["operator_message"],
        "capability_id": unlock_readiness["next_capability_id"],
        "mode": "lab",
        "current_level": "L4",
        "next_level": "L5",
        "status": "approval_required",
        "blocked_reason": unlock_readiness["next_unlock"],
        "next_unlock": unlock_readiness["next_unlock"],
        "next_evidence_count": unlock_readiness["next_required_evidence_count"],
        "external_effects_allowed": False,
        "rollback_required": True,
    }
    control_system = capability_panel["metadata"]["control_system_summary"]
    assert control_system["summary_id"] == "control_system.foundation"
    assert control_system["task"] == "Mullu Developer Workflow v1"
    assert control_system["status"] == "preflight_ready"
    assert control_system["recommended_mode"] == "fast"
    assert control_system["lab_mode_allowed"] is True
    assert control_system["capability_count"] == 12
    assert control_system["pending_unlock_count"] >= 1
    assert control_system["safe_candidate_count"] == 7
    assert control_system["dangerous_blocker_count"] == 7
    assert control_system["next_unlock"] == "approval"
    assert "approval" in control_system["next_required_evidence"]
    assert control_system["risk"] == "low, local lab only"
    assert control_system["action_needed"] == "review diff receipt before approving pull request candidate"
    assert "Control system in fast mode" in control_system["operator_message"]
    assert control_system["execution_boundary"] == "local_lab_only"
    assert control_system["external_effects_allowed"] is False
    assert control_system["control_summary"] == {
        "contract_id": "operator_dashboard_control_summary.v1",
        "summary_id": "control_system.control_summary.v1",
        "operator_message": (
            "Control system in fast mode; 7 safe local candidates; "
            "next unlock approval"
        ),
        "action_banner": (
            "Control system in fast mode; 7 safe local candidates; "
            "next unlock approval"
        ),
        "capability_id": "control_system.foundation",
        "mode": "lab",
        "current_level": "L4",
        "next_level": "L5",
        "status": "preflight_ready",
        "blocked_reason": "none",
        "next_unlock": "approval",
        "next_evidence_count": control_system["next_required_evidence_count"],
        "external_effects_allowed": False,
        "rollback_required": True,
    }
    assert capability_panel["metadata"]["next_unlock_queue_count"] >= 1
    assert capability_panel["metadata"]["capability_passport_count"] == 12
    pr_unlock = next(item for item in unlock_queue if item["capability_id"] == "software_dev.pr_candidate.prepare")
    assert pr_unlock["next_unlock"] == "approval"
    assert "approval" in pr_unlock["required_evidence"]
    change_passport = next(item for item in passports if item["capability_id"] == "software_dev.change.run")
    assert change_passport["unlock_level"] == "L4"
    assert change_passport["status"] == "approval_required"
    assert change_passport["operating_boundary"] == "lab"
    assert change_passport["fast_mode_admission"] == "allowed_lab"
    assert change_passport["rollback_default"] is True
    assert mode_selector["default_mode"] == "balanced"
    assert mode_selector["foundation_recommended_mode"] == "fast"
    assert mode_selector["summary"]["fast"]["allowed_count"] >= 1
    friction_mode = capability_panel["metadata"]["friction_mode_summary"]
    assert friction_mode["summary_id"] == "friction_mode.foundation"
    assert friction_mode["default_mode"] == "balanced"
    assert friction_mode["foundation_recommended_mode"] == "fast"
    assert friction_mode["strict_approval_required_count"] == mode_selector["summary"]["strict"]["approval_required_count"]
    assert friction_mode["balanced_approval_required_count"] == mode_selector["summary"]["balanced"]["approval_required_count"]
    assert friction_mode["fast_allowed_count"] == mode_selector["summary"]["fast"]["allowed_count"]
    assert "fast mode recommended for local lab" in friction_mode["operator_message"]
    assert friction_mode["execution_boundary"] == "local_lab_only"
    assert friction_mode["external_effects_allowed"] is False
    mode_change = next(item for item in mode_selector["capabilities"] if item["capability_id"] == "software_dev.change.run")
    assert mode_change["strict"] == "approval_required"
    assert mode_change["balanced"] == "approval_required"
    assert mode_change["fast"] == "allowed_lab"
    assert mode_change["recommended_mode"] == "fast"
    assert sandbox_to_pr_policy["policy_ready"] is True
    assert sandbox_to_pr_policy["change_passport_present"] is True
    assert sandbox_to_pr_policy["pr_passport_present"] is True
    assert sandbox_to_pr_policy["rollback_default"] is True
    assert sandbox_to_pr_policy["approval_required"] is True
    assert "write_docs" in capability_panel["metadata"]["safe_automatic_zones"]
    assert "deploy" in capability_panel["metadata"]["dangerous_zones"]
    assert capability_panel["metadata"]["safe_local_action_queue_summary"] == {
        "summary_id": "safe_local_action_queue.foundation",
        "queue_status": "ready",
        "candidate_count": 7,
        "first_candidate_id": "safe_zone.write_docs",
        "first_zone": "write_docs",
        "first_action": "Prepare documentation update in local sandbox",
        "recommended_mode": "fast",
        "approval_required": False,
        "local_execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "operator_message": (
            "7 safe local actions queued for fast mode; "
            "approval not required for local preparation"
        ),
        "control_summary": {
            "contract_id": "operator_dashboard_control_summary.v1",
            "summary_id": "safe_local_action_queue.control_summary.v1",
            "operator_message": (
                "7 safe local actions queued for fast mode; "
                "approval not required for local preparation"
            ),
            "action_banner": (
                "7 safe local actions queued for fast mode; "
                "approval not required for local preparation"
            ),
            "capability_id": "safe_local_action_queue.foundation",
            "mode": "lab",
            "current_level": "L3",
            "next_level": "L4",
            "status": "preflight_ready",
            "blocked_reason": "none",
            "next_unlock": "none",
            "next_evidence_count": 0,
            "external_effects_allowed": False,
            "rollback_required": False,
        },
    }
    assert capability_panel["metadata"]["dangerous_action_blocker_summary"] == {
        "summary_id": "dangerous_action_blocker.foundation",
        "blocker_status": "blocked",
        "blocker_count": 7,
        "first_blocker_id": "dangerous_zone.delete_files",
        "first_zone": "delete_files",
        "first_reason": "dangerous_zone_requires_explicit_approval",
        "required_evidence": [
            "operator_approval",
            "rollback_plan",
            "effect_receipt",
        ],
        "approval_required": True,
        "rollback_required": True,
        "real_world_execution_boundary": "real_world",
        "external_effects_allowed": False,
        "operator_message": (
            "7 dangerous real-world zones blocked; "
            "approval, rollback, and effect receipt required before execution"
        ),
        "control_summary": {
            "contract_id": "operator_dashboard_control_summary.v1",
            "summary_id": "dangerous_action_blocker.control_summary.v1",
            "operator_message": (
                "7 dangerous real-world zones blocked; "
                "approval, rollback, and effect receipt required before execution"
            ),
            "action_banner": (
                "7 dangerous real-world zones blocked; "
                "approval, rollback, and effect receipt required before execution"
            ),
            "capability_id": "dangerous_action_blocker.foundation",
            "mode": "real_world",
            "current_level": "L0",
            "next_level": "L9",
            "status": "blocked",
            "blocked_reason": "dangerous_zone_requires_explicit_approval",
            "next_unlock": "approval",
            "next_evidence_count": 3,
            "external_effects_allowed": False,
            "rollback_required": True,
        },
    }
    assert rollback["rollback_default_count"] >= 1
    assert rollback["rollback_required_count"] >= 1
    assert rollback["rollback_receipt_source"] == (
        "developer_workflow_run.software_receipt_binding.stage_evidence.rollback_completed"
    )
    assert approval_panel["source_surface"] == "operator_approval_history"
    assert approval_panel["metadata"]["approval_history_href"] == "/operator/approvals"
    assert proof_panel["source_surface"] == "operator_receipt_viewer"
    assert proof_panel["metadata"]["receipt_viewer_href"] == "/operator/receipts"
    assert workflow_panel["source_surface"] == "operator_workflow_monitor"
    assert workflow_panel["metadata"]["current_task_href"] == "/operator/current-task"
    assert workflow_panel["metadata"]["plan_review_href"] == "/operator/plan-review"
    assert workflow_panel["metadata"]["developer_workflow_href"] == "/operator/developer-workflow"
    assert workflow_panel["metadata"]["developer_workflow_read_model_href"] == "/operator/developer-workflow/read-model"
    workflow_monitor_summary = workflow_panel["metadata"]["workflow_monitor_summary"]
    assert workflow_monitor_summary["monitor_status"] == "monitoring"
    assert workflow_monitor_summary["current_task_id"] == "sandbox_change"
    assert workflow_monitor_summary["current_task_count"] >= 1
    assert workflow_monitor_summary["plan_review_count"] >= 1
    assert workflow_monitor_summary["blocked_count"] == 0
    assert workflow_monitor_summary["review_count"] == 0
    assert workflow_monitor_summary["workflow_status"] == "waiting_for_approval"
    assert workflow_monitor_summary["readiness_status"] == "awaiting_receipts"
    assert workflow_monitor_summary["blocker"] == "sandbox_receipts_incomplete"
    assert workflow_monitor_summary["next_action"] == "complete sandbox patch, test, diff, and terminal receipts"
    assert workflow_monitor_summary["execution_boundary"] == "local_lab_only"
    assert workflow_monitor_summary["external_effects_allowed"] is False
    action_card = workflow_panel["metadata"]["operator_action_card"]
    assert action_card["card_id"] == "developer_workflow_next_action"
    assert action_card["title"] == "Next developer workflow action"
    assert action_card["status"] == "awaiting_receipts"
    assert action_card["reason"] == "sandbox_receipts_incomplete"
    assert action_card["primary_action"] == "complete sandbox patch, test, diff, and terminal receipts"
    assert action_card["primary_href"] == "/operator/control-tower/status-receipt?focus_id=sandbox_patch_receipt"
    assert action_card["focus_id"] == "sandbox_patch_receipt"
    assert action_card["task_id"] == "sandbox_change"
    assert action_card["risk"] == "low, local lab only"
    assert action_card["execution_boundary"] == "local_lab_only"
    assert action_card["approval_required"] is False
    assert action_card["external_effects_allowed"] is False
    assert workflow_panel["metadata"]["next_action_summary"] == {
        "summary_id": "next_action.foundation",
        "status": "awaiting_receipts",
        "reason": "sandbox_receipts_incomplete",
        "primary_action": "complete sandbox patch, test, diff, and terminal receipts",
        "primary_href": "/operator/control-tower/status-receipt?focus_id=sandbox_patch_receipt",
        "focus_id": "sandbox_patch_receipt",
        "focus_label": "Sandbox patch receipt",
        "focus_status": "pending",
        "focus_source": "workflow_monitor.metadata.developer_workflow_run.receipt_checklist.sandbox_patch_receipt",
        "required_evidence": [
            "sandbox_patch_receipt",
            "test_gate_receipt",
            "diff_review_receipt",
            "terminal_receipt",
        ],
        "required_evidence_count": 4,
        "approval_required": False,
        "risk": "low, local lab only",
        "operator_message": (
            "Next action complete sandbox patch, test, diff, and terminal receipts; "
            "focus sandbox_patch_receipt"
        ),
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }
    assert workflow_panel["metadata"]["approval_readiness_summary"] == {
        "summary_id": "approval_readiness.foundation",
        "approval_required": True,
        "operator_approval_status": "pending",
        "approval_missing": True,
        "current_blocker": "sandbox_receipts_incomplete",
        "approval_boundary": "before_pr_or_real_world_effect",
        "next_approval_action": "complete sandbox receipts before requesting approval",
        "approval_target_href": "/operator/control-tower/status-receipt?focus_id=sandbox_patch_receipt",
        "pr_candidate_status": "pending",
        "ready_for_pr_candidate_preparation": False,
        "external_pr_execution_allowed": False,
        "operator_message": "Approval pending; sandbox_receipts_incomplete remains current blocker",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }
    assert workflow_panel["metadata"]["operator_decision_summary"] == {
        "summary_id": "operator_decision.foundation",
        "decision_status": "awaiting_receipts",
        "decision_kind": "evidence_collection",
        "current_milestone": "collect_sandbox_receipts",
        "current_blocker": "sandbox_receipts_incomplete",
        "recommended_action": "complete sandbox patch, test, diff, and terminal receipts",
        "action_href": "/operator/control-tower/status-receipt?focus_id=sandbox_patch_receipt",
        "next_evidence_id": "sandbox_patch_receipt",
        "operator_review_required_now": False,
        "operator_review_required_before_external_effect": True,
        "approval_status": "pending",
        "local_continuation_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "operator_message": (
            "Decision collect_sandbox_receipts can continue in local lab; "
            "approval pending before PR or real-world effect"
        ),
    }
    assert workflow_panel["metadata"]["friction_reduction_summary"] == {
        "summary_id": "friction_reduction.foundation",
        "reduction_status": "local_continuation_ready",
        "current_milestone": "collect_sandbox_receipts",
        "current_blocker": "sandbox_receipts_incomplete",
        "local_continuation_allowed": True,
        "pending_evidence_count": 7,
        "next_evidence_id": "sandbox_patch_receipt",
        "approval_boundary": "before_pr_or_real_world_effect",
        "operator_review_required_now": False,
        "external_effects_allowed": False,
        "operator_message": (
            "Friction reduced to collect_sandbox_receipts; continue local evidence collection, "
            "while PR and real-world effects remain approval-bound"
        ),
    }
    assert workflow_panel["metadata"]["sandbox_receipt_bundle_summary"] == {
        "status": "not_attached",
        "completed_count": 0,
        "required_count": 0,
        "receipt_count": 0,
        "next_receipt_id": "sandbox_patch_receipt",
        "next_receipt_status": "pending",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }
    assert workflow_panel["metadata"]["developer_workflow_readiness_summary"] == {
        "workflow_status": "waiting_for_approval",
        "current_task_id": "sandbox_change",
        "readiness_status": "awaiting_receipts",
        "packet_status": "awaiting_receipts",
        "blocker": "sandbox_receipts_incomplete",
        "receipt_completed_count": 0,
        "receipt_required_count": 4,
        "checklist_completed_required_count": 0,
        "checklist_required_count": 6,
        "operator_approval_status": "pending",
        "pr_candidate_status": "pending",
        "rollback_receipt_status": "not_recorded",
        "next_action": "complete sandbox patch, test, diff, and terminal receipts",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }
    assert workflow_panel["metadata"]["developer_workflow_milestone_summary"] == {
        "summary_id": "developer_workflow_milestone.foundation",
        "workflow_status": "waiting_for_approval",
        "readiness_status": "awaiting_receipts",
        "current_task_id": "sandbox_change",
        "current_milestone": "collect_sandbox_receipts",
        "blocker": "sandbox_receipts_incomplete",
        "next_action": "complete sandbox patch, test, diff, and terminal receipts",
        "receipt_completed_count": 0,
        "receipt_required_count": 4,
        "operator_approval_status": "pending",
        "pr_candidate_status": "pending",
        "operator_message": (
            "Developer workflow milestone collect_sandbox_receipts; next action "
            "complete sandbox patch, test, diff, and terminal receipts"
        ),
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }
    assert workflow_panel["metadata"]["local_rollback_flow_readiness_summary"] == {
        "readiness_verdict": "awaiting_selection",
        "command_status": "awaiting_selection",
        "selected_artifact_count": 0,
        "receipt_available_count": 0,
        "receipt_required_count": 3,
        "next_action": "select at least one generated artifact before running rollback flow",
        "dry_run_required": True,
        "execution_requires_execute_flag": True,
        "external_effects_allowed": False,
    }
    assert workflow_panel["metadata"]["evidence_progress_summary"] == {
        "summary_id": "evidence_progress.foundation",
        "status": "awaiting_evidence",
        "completed_count": 0,
        "required_count": 7,
        "pending_count": 7,
        "next_evidence_id": "sandbox_patch_receipt",
        "next_action": "attach before state, after state, diff, command, and rollback receipt",
        "blocker": "sandbox_receipts_incomplete",
        "sandbox_receipt_completed_count": 0,
        "sandbox_receipt_required_count": 4,
        "sandbox_bundle_completed_count": 0,
        "sandbox_bundle_required_count": 0,
        "rollback_receipt_available_count": 0,
        "rollback_receipt_required_count": 3,
        "pr_next_evidence_count": 7,
        "operator_message": "0/7 local evidence receipts complete; next sandbox_patch_receipt",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }
    assert workflow_panel["metadata"]["local_rollback_receipts_summary"] == {
        "summary_status": "not_attached",
        "approval_status": "pending",
        "execution_status": "blocked_no_approval",
        "execution_mode": "dry_run",
        "generated_artifact_count": 0,
        "selected_artifact_count": 0,
        "attached_receipt_count": 0,
        "required_receipt_count": 3,
        "delete_execution_allowed": False,
        "rollback_execution_performed": False,
        "external_effects_allowed": False,
    }
    assert workflow_panel["metadata"]["developer_workflow_run"]["status"] == "waiting_for_approval"
    assert workflow_panel["metadata"]["developer_workflow_run"]["current_task_id"] == "sandbox_change"
    assert workflow_panel["metadata"]["developer_workflow_run"]["status_counts"]["committed"] == 4
    checklist = workflow_panel["metadata"]["developer_workflow_run"]["receipt_checklist"]
    sandbox_check = next(item for item in checklist if item["checklist_id"] == "sandbox_patch_receipt")
    assert sandbox_check["status"] == "pending"
    assert workflow_panel["metadata"]["developer_workflow_run"]["receipt_checklist_required_count"] == 6
    assert workflow_panel["metadata"]["developer_workflow_run"]["receipt_checklist_completed_required_count"] == 0
    assert workflow_panel["metadata"]["developer_workflow_run"]["receipt_checklist_pending_required_count"] == 6
    assert workflow_panel["metadata"]["developer_workflow_run"]["rollback_receipt_status"] == "not_recorded"
    assert workflow_panel["metadata"]["developer_workflow_run"]["rollback_receipt_count"] == 0
    readiness = workflow_panel["metadata"]["developer_workflow_run"]["sandbox_to_pr_readiness"]
    assert readiness["readiness_status"] == "awaiting_receipts"
    assert readiness["receipt_checklist_ready"] is False
    assert readiness["receipt_checklist_completed_count"] == 0
    assert readiness["receipt_checklist_required_count"] == 4
    assert readiness["operator_approval_status"] == "pending"
    assert readiness["pr_candidate_status"] == "pending"
    assert readiness["rollback_receipt_status"] == "not_recorded"
    assert readiness["next_action"] == "complete sandbox patch, test, diff, and terminal receipts"
    packet = workflow_panel["metadata"]["sandbox_to_pr_packet"]
    focus = workflow_panel["metadata"]["sandbox_to_pr_focus"]
    sandbox_to_pr_summary = workflow_panel["metadata"]["sandbox_to_pr_summary"]
    attachment_packet = workflow_panel["metadata"]["sandbox_receipt_attachment_packet"]
    attachment_readiness_summary = workflow_panel["metadata"]["sandbox_receipt_attachment_readiness_summary"]
    pr_readiness = workflow_panel["metadata"]["pr_readiness_bundle"]
    pr_readiness_summary = workflow_panel["metadata"]["pr_readiness_summary"]
    operator_receipt_summary = workflow_panel["metadata"]["developer_workflow_operator_receipt_summary"]
    proof_readiness_summary = workflow_panel["metadata"]["local_sandbox_proof_readiness_summary"]
    packet_schema = json.loads(SANDBOX_TO_PR_PACKET_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(packet_schema).validate(packet)
    assert packet["packet_id"] == "sandbox_to_pr_preparation_packet.v1"
    assert packet["status"] == "awaiting_receipts"
    assert packet["blocker"] == "sandbox_receipts_incomplete"
    assert packet["external_effects_allowed"] is False
    assert packet["execution_boundary"] == "local_lab_only"
    assert packet["policy"]["ready"] is True
    assert packet["policy"]["rollback_default"] is True
    assert packet["receipts"]["ready"] is False
    assert packet["approval"]["required"] is True
    evidence = {item["evidence_id"]: item for item in packet["required_evidence"]}
    assert evidence["capability_passports"]["status"] == "complete"
    assert evidence["sandbox_receipts"]["status"] == "pending"
    assert evidence["operator_approval"]["status"] == "pending"
    assert evidence["pr_candidate"]["status"] == "pending"
    assert [item["evidence_id"] for item in packet["next_evidence"]] == [
        "sandbox_patch_receipt",
        "test_gate_receipt",
        "diff_review_receipt",
        "terminal_receipt",
    ]
    assert all(item["status"] == "pending" for item in packet["next_evidence"])
    assert focus["focus_id"] == "sandbox_patch_receipt"
    assert focus["label"] == "Sandbox patch receipt"
    assert focus["status"] == "pending"
    assert focus["action"] == "attach before state, after state, diff, command, and rollback receipt"
    assert focus["blocker"] == "sandbox_receipts_incomplete"
    assert focus["next_action"] == "complete sandbox patch, test, diff, and terminal receipts"
    assert sandbox_to_pr_summary == {
        "status": "awaiting_receipts",
        "blocker": "sandbox_receipts_incomplete",
        "focus_id": "sandbox_patch_receipt",
        "focus_status": "pending",
        "next_action": "complete sandbox patch, test, diff, and terminal receipts",
        "next_evidence_count": 4,
        "receipt_completed_count": 0,
        "receipt_required_count": 4,
        "operator_approval_status": "pending",
        "pr_candidate_status": "pending",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }
    assert focus["source"] == (
        "workflow_monitor.metadata.developer_workflow_run.receipt_checklist.sandbox_patch_receipt"
    )
    attachment_schema = json.loads(
        (_ROOT / "schemas" / "developer_workflow_sandbox_receipt_attachment_packet.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(attachment_schema).validate(attachment_packet)
    assert attachment_packet["packet_id"] == "developer_workflow_sandbox_receipt_attachment_packet.v1"
    assert attachment_packet["packet_status"] == "awaiting_attachments"
    assert attachment_packet["external_effects_allowed"] is False
    assert attachment_packet["completed_count"] == 0
    assert attachment_packet["required_count"] == 4
    assert attachment_packet["next_attachment"]["receipt_id"] == "sandbox_patch_receipt"
    assert attachment_packet["attachments"][0]["status"] == "awaiting_attachment"
    assert attachment_packet["attachments"][0]["action"] == (
        "attach before state, after state, diff, command, and rollback receipt"
    )
    assert attachment_readiness_summary == {
        "packet_status": "awaiting_attachments",
        "completed_count": 0,
        "required_count": 4,
        "next_receipt_id": "sandbox_patch_receipt",
        "next_label": "Sandbox patch receipt",
        "next_status": "awaiting_attachment",
        "next_action": "attach before state, after state, diff, command, and rollback receipt",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }
    assert proof_readiness_summary == {
        "proof_status": "not_attached",
        "ok": False,
        "bundle_status": "unknown",
        "attachment_packet_status": "unknown",
        "next_attachment_id": "unknown",
        "pr_readiness_status": "unknown",
        "completed_count": 0,
        "required_count": 0,
        "execution_performed": False,
        "external_effects_allowed": False,
    }
    assert pr_readiness["bundle_id"] == "pr_readiness_bundle.v1"
    assert pr_readiness["readiness_status"] == "awaiting_sandbox_receipts"
    assert pr_readiness["ready_for_external_pr_execution"] is False
    assert pr_readiness["first_blocker"] == "sandbox_receipts"
    assert pr_readiness["external_effects_allowed"] is False
    assert pr_readiness["pr_creation_allowed"] is False
    assert pr_readiness["branch_push_allowed"] is False
    assert pr_readiness["next_evidence"][0] == "sandbox_receipts"
    assert pr_readiness_summary == {
        "readiness_status": "awaiting_sandbox_receipts",
        "ready_for_external_pr_execution": False,
        "first_blocker": "sandbox_receipts",
        "next_evidence_count": 7,
        "receipt_completed_count": 0,
        "receipt_required_count": 4,
        "preview_only": True,
        "execution_performed": False,
        "external_effects_allowed": False,
        "pr_creation_allowed": False,
        "branch_push_allowed": False,
    }
    assert operator_receipt_summary == {
        "solver_outcome": "AwaitingEvidence",
        "readiness_status": "awaiting_sandbox_receipts",
        "ready_for_external_pr_execution": False,
        "command_preview_rendered": False,
        "next_evidence_count": 7,
        "local_candidate_ready": False,
        "pr_tool_admitted": False,
        "external_approval_status": "pending",
        "rollback_required": True,
        "rollback_command_count": 0,
        "evidence_chain_count": 4,
        "execution_performed": False,
        "external_effects_allowed": False,
    }
    friction_next_evidence = capability_panel["metadata"]["sandbox_to_pr_now"]["next_evidence"]
    assert [
        (item["evidence_id"], item["action"], item["source"])
        for item in packet["next_evidence"]
    ] == [
        (item["evidence_id"], item["action"], item["source"])
        for item in friction_next_evidence
    ]
    assert workflow["workflow_id"] == "mullu_developer_workflow.v1"
    assert workflow["status"] == "preflight_ready"
    assert workflow["real_world_effects_allowed"] is False
    assert summary["task"] == "Mullu Developer Workflow v1"
    assert summary["risk"] == "low, local lab only"
    assert "raw_tool_surface" not in capability_panel["metadata"]


def test_operator_control_tower_can_opt_into_local_sandbox_receipt_bundle(
    monkeypatch,
    tmp_path: Path,
) -> None:
    bundle_path = tmp_path / "developer_workflow_sandbox_receipt_bundle.collected.json"
    bundle_path.write_text(json.dumps(_sandbox_receipt_bundle(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path = tmp_path / "developer_workflow_local_sandbox_proof_report.generated.json"
    report_path.write_text(json.dumps(_local_sandbox_proof_report(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rollback_path = tmp_path / "developer_workflow_local_rollback_summary_packet.generated.json"
    rollback_path.write_text(
        json.dumps(_local_rollback_summary_packet(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    rollback_approval_path = tmp_path / "developer_workflow_local_rollback_approval_packet.generated.json"
    rollback_approval_path.write_text(
        json.dumps(_local_rollback_approval_packet(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    rollback_execution_path = tmp_path / "developer_workflow_local_rollback_execution_receipt.generated.json"
    rollback_execution_path.write_text(
        json.dumps(_local_rollback_execution_receipt(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(server_module, "LOCAL_SANDBOX_RECEIPT_BUNDLE_PATH", bundle_path)
    monkeypatch.setattr(server_module, "LOCAL_SANDBOX_PROOF_REPORT_PATH", report_path)
    monkeypatch.setattr(server_module, "LOCAL_ROLLBACK_SUMMARY_PACKET_PATH", rollback_path)
    monkeypatch.setattr(server_module, "LOCAL_ROLLBACK_APPROVAL_PACKET_PATH", rollback_approval_path)
    monkeypatch.setattr(server_module, "LOCAL_ROLLBACK_EXECUTION_RECEIPT_PATH", rollback_execution_path)
    gate = build_software_dev_capability_admission_gate(clock=_clock)
    app = create_gateway_app(
        platform=StubPlatform(),
        capability_admission_gate_override=gate,
    )
    client = TestClient(app)

    response = client.get(
        "/operator/control-tower/read-model"
        "?domain=software_dev&include_local_sandbox_receipts=true"
    )

    assert response.status_code == 200
    payload = response.json()
    panels = {item["panel"]: item for item in payload["panels"]}
    workflow_run = panels["workflow_monitor"]["metadata"]["developer_workflow_run"]
    workflow_readiness_summary = panels["workflow_monitor"]["metadata"]["developer_workflow_readiness_summary"]
    bundle_summary = panels["workflow_monitor"]["metadata"]["developer_workflow_run"]["sandbox_receipt_bundle_receipts"]
    bundle_readiness_summary = panels["workflow_monitor"]["metadata"]["sandbox_receipt_bundle_summary"]
    packet = panels["workflow_monitor"]["metadata"]["sandbox_to_pr_packet"]
    sandbox_to_pr_summary = panels["workflow_monitor"]["metadata"]["sandbox_to_pr_summary"]
    attachment_packet = panels["workflow_monitor"]["metadata"]["sandbox_receipt_attachment_packet"]
    attachment_readiness_summary = panels["workflow_monitor"]["metadata"][
        "sandbox_receipt_attachment_readiness_summary"
    ]
    pr_readiness = panels["workflow_monitor"]["metadata"]["pr_readiness_bundle"]
    pr_readiness_summary = panels["workflow_monitor"]["metadata"]["pr_readiness_summary"]
    operator_receipt_summary = panels["workflow_monitor"]["metadata"]["developer_workflow_operator_receipt_summary"]
    proof_report = panels["workflow_monitor"]["metadata"]["local_sandbox_proof_report"]
    proof_readiness_summary = panels["workflow_monitor"]["metadata"]["local_sandbox_proof_readiness_summary"]
    rollback_summary = panels["workflow_monitor"]["metadata"]["local_rollback_summary_packet"]
    rollback_approval = panels["workflow_monitor"]["metadata"]["local_rollback_approval_packet"]
    rollback_execution = panels["workflow_monitor"]["metadata"]["local_rollback_execution_receipt"]
    rollback_receipts_summary = panels["workflow_monitor"]["metadata"]["local_rollback_receipts_summary"]
    rollback_flow_command = panels["workflow_monitor"]["metadata"]["local_rollback_flow_command"]
    rollback_readiness_summary = panels["workflow_monitor"]["metadata"]["local_rollback_flow_readiness_summary"]
    checklist = {item["checklist_id"]: item for item in workflow_run["receipt_checklist"]}
    assert workflow_readiness_summary == {
        "workflow_status": "waiting_for_approval",
        "current_task_id": "test_run",
        "readiness_status": "awaiting_receipts",
        "packet_status": "awaiting_receipts",
        "blocker": "sandbox_receipts_incomplete",
        "receipt_completed_count": 1,
        "receipt_required_count": 4,
        "checklist_completed_required_count": 1,
        "checklist_required_count": 6,
        "operator_approval_status": "pending",
        "pr_candidate_status": "pending",
        "rollback_receipt_status": "not_recorded",
        "next_action": "complete sandbox patch, test, diff, and terminal receipts",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }
    assert workflow_run["receipt_checklist_completed_required_count"] == 1
    assert workflow_run["sandbox_receipt_bundle_status"] == "awaiting_receipts"
    assert workflow_run["sandbox_receipt_bundle_completed_count"] == 1
    assert workflow_run["sandbox_receipt_bundle_required_count"] == 4
    assert bundle_summary[0]["receipt_id"] == "sandbox_patch_receipt"
    assert bundle_summary[0]["evidence_refs"] == ["proof://developer-workflow-v1/sandbox-patch/collected"]
    assert bundle_readiness_summary == {
        "status": "awaiting_receipts",
        "completed_count": 1,
        "required_count": 4,
        "receipt_count": 4,
        "next_receipt_id": "test_gate_receipt",
        "next_receipt_status": "pending",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }
    assert workflow_run["sandbox_to_pr_readiness"]["receipt_checklist_completed_count"] == 1
    assert checklist["sandbox_patch_receipt"]["status"] == "complete"
    assert checklist["test_gate_receipt"]["status"] == "pending"
    assert packet["receipts"]["completed_count"] == 1
    assert packet["external_effects_allowed"] is False
    assert sandbox_to_pr_summary == {
        "status": "awaiting_receipts",
        "blocker": "sandbox_receipts_incomplete",
        "focus_id": "sandbox_patch_receipt",
        "focus_status": "pending",
        "next_action": "complete sandbox patch, test, diff, and terminal receipts",
        "next_evidence_count": 4,
        "receipt_completed_count": 1,
        "receipt_required_count": 4,
        "operator_approval_status": "pending",
        "pr_candidate_status": "pending",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }
    assert attachment_packet["completed_count"] == 1
    assert attachment_packet["required_count"] == 4
    assert attachment_packet["attachments"][0]["status"] == "attached"
    assert attachment_packet["attachments"][0]["evidence_refs"] == [
        "proof://developer-workflow-v1/sandbox-patch/collected"
    ]
    assert attachment_packet["next_attachment"]["receipt_id"] == "test_gate_receipt"
    assert attachment_readiness_summary == {
        "packet_status": "awaiting_attachments",
        "completed_count": 1,
        "required_count": 4,
        "next_receipt_id": "test_gate_receipt",
        "next_label": "Test gate receipt",
        "next_status": "awaiting_attachment",
        "next_action": "attach bounded local test command receipt and observed result",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }
    assert pr_readiness["readiness_status"] == "awaiting_sandbox_receipts"
    assert pr_readiness["receipt_progress"]["completed_count"] == 1
    assert pr_readiness["receipt_progress"]["required_count"] == 4
    assert pr_readiness_summary == {
        "readiness_status": "awaiting_sandbox_receipts",
        "ready_for_external_pr_execution": False,
        "first_blocker": "sandbox_receipts",
        "next_evidence_count": 7,
        "receipt_completed_count": 1,
        "receipt_required_count": 4,
        "preview_only": True,
        "execution_performed": False,
        "external_effects_allowed": False,
        "pr_creation_allowed": False,
        "branch_push_allowed": False,
    }
    assert operator_receipt_summary == {
        "solver_outcome": "AwaitingEvidence",
        "readiness_status": "awaiting_sandbox_receipts",
        "ready_for_external_pr_execution": False,
        "command_preview_rendered": False,
        "next_evidence_count": 7,
        "local_candidate_ready": False,
        "pr_tool_admitted": False,
        "external_approval_status": "pending",
        "rollback_required": True,
        "rollback_command_count": 0,
        "evidence_chain_count": 4,
        "execution_performed": False,
        "external_effects_allowed": False,
    }
    assert proof_report["status"] == "attached"
    assert proof_report["ok"] is True
    assert proof_report["attachment_packet_status"] == "awaiting_attachments"
    assert proof_report["next_attachment_id"] == "test_gate_receipt"
    assert proof_report["generated_artifacts"]["sandbox_receipt_attachment_packet"].endswith(
        "developer_workflow_sandbox_receipt_attachment_packet.generated.json"
    )
    assert proof_readiness_summary == {
        "proof_status": "attached",
        "ok": True,
        "bundle_status": "awaiting_receipts",
        "attachment_packet_status": "awaiting_attachments",
        "next_attachment_id": "test_gate_receipt",
        "pr_readiness_status": "awaiting_sandbox_receipts",
        "completed_count": 1,
        "required_count": 4,
        "execution_performed": False,
        "external_effects_allowed": False,
    }
    assert rollback_summary["status"] == "attached"
    assert rollback_summary["packet_status"] == "rollback_ready"
    assert rollback_summary["generated_artifact_count"] == 10
    assert rollback_summary["rollback_execution_performed"] is False
    assert rollback_summary["external_effects_allowed"] is False
    assert rollback_summary["artifacts"][0]["required_confirmation"] is True
    assert "Remove-Item -LiteralPath" in rollback_summary["artifacts"][0]["rollback_command"]
    assert rollback_approval["status"] == "attached"
    assert rollback_approval["packet_status"] == "awaiting_operator_approval"
    assert rollback_approval["approval_status"] == "pending"
    assert rollback_approval["selected_artifact_count"] == 0
    assert rollback_approval["delete_execution_allowed"] is False
    assert rollback_execution["status"] == "attached"
    assert rollback_execution["execution_status"] == "blocked_no_approval"
    assert rollback_execution["execution_mode"] == "dry_run"
    assert rollback_execution["rollback_execution_performed"] is False
    assert rollback_execution["external_effects_allowed"] is False
    assert rollback_receipts_summary == {
        "summary_status": "attached",
        "approval_status": "pending",
        "execution_status": "blocked_no_approval",
        "execution_mode": "dry_run",
        "generated_artifact_count": 10,
        "selected_artifact_count": 0,
        "attached_receipt_count": 3,
        "required_receipt_count": 3,
        "delete_execution_allowed": False,
        "rollback_execution_performed": False,
        "external_effects_allowed": False,
    }
    assert rollback_flow_command["status"] == "awaiting_selection"
    assert rollback_flow_command["action_label"] == "Run local rollback dry-run"
    assert rollback_flow_command["next_action"] == (
        "select at least one generated artifact before running rollback flow"
    )
    assert rollback_flow_command["selected_artifact_ids"] == []
    assert rollback_flow_command["rollback_summary_path"].endswith(
        "developer_workflow_local_rollback_summary_packet.generated.json"
    )
    assert rollback_flow_command["approval_packet_path"].endswith(
        "developer_workflow_local_rollback_approval_packet.generated.json"
    )
    assert rollback_flow_command["dry_run_receipt_path"].endswith(
        "developer_workflow_local_rollback_execution_receipt.generated.json"
    )
    assert rollback_flow_command["execution_receipt_path"].endswith(
        "developer_workflow_local_rollback_execution_receipt.generated.json"
    )
    assert rollback_flow_command["rollback_summary_href"].endswith("receipt_id=summary")
    assert rollback_flow_command["approval_packet_href"].endswith("receipt_id=approval")
    assert rollback_flow_command["dry_run_receipt_href"].endswith("receipt_id=execution")
    assert rollback_flow_command["execution_receipt_href"].endswith("receipt_id=execution")
    assert rollback_flow_command["receipt_availability"] == {
        "summary": "available",
        "approval": "available",
        "execution": "available",
        "available_count": 3,
        "required_count": 3,
    }
    assert rollback_flow_command["readiness_verdict"] == "awaiting_selection"
    assert "run_developer_workflow_local_rollback_flow.py" in rollback_flow_command["command"]
    assert "--artifact-id <artifact_id>" in rollback_flow_command["command"]
    assert "--execute" not in rollback_flow_command["command"]
    assert rollback_flow_command["execute_command"].endswith("--json --execute")
    assert rollback_flow_command["dry_run_required"] is True
    assert rollback_flow_command["execution_requires_execute_flag"] is True
    assert rollback_flow_command["external_effects_allowed"] is False
    assert rollback_readiness_summary == {
        "readiness_verdict": "awaiting_selection",
        "command_status": "awaiting_selection",
        "selected_artifact_count": 0,
        "receipt_available_count": 3,
        "receipt_required_count": 3,
        "next_action": "select at least one generated artifact before running rollback flow",
        "dry_run_required": True,
        "execution_requires_execute_flag": True,
        "external_effects_allowed": False,
    }


def test_operator_control_tower_html_shows_opted_in_local_sandbox_bundle_status(
    monkeypatch,
    tmp_path: Path,
) -> None:
    bundle_path = tmp_path / "developer_workflow_sandbox_receipt_bundle.collected.json"
    bundle_path.write_text(json.dumps(_sandbox_receipt_bundle(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path = tmp_path / "developer_workflow_local_sandbox_proof_report.generated.json"
    report_path.write_text(json.dumps(_local_sandbox_proof_report(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rollback_path = tmp_path / "developer_workflow_local_rollback_summary_packet.generated.json"
    rollback_path.write_text(
        json.dumps(_local_rollback_summary_packet(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    rollback_approval_path = tmp_path / "developer_workflow_local_rollback_approval_packet.generated.json"
    rollback_approval_path.write_text(
        json.dumps(_local_rollback_approval_packet(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    rollback_execution_path = tmp_path / "developer_workflow_local_rollback_execution_receipt.generated.json"
    rollback_execution_path.write_text(
        json.dumps(_local_rollback_execution_receipt(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(server_module, "LOCAL_SANDBOX_RECEIPT_BUNDLE_PATH", bundle_path)
    monkeypatch.setattr(server_module, "LOCAL_SANDBOX_PROOF_REPORT_PATH", report_path)
    monkeypatch.setattr(server_module, "LOCAL_ROLLBACK_SUMMARY_PACKET_PATH", rollback_path)
    monkeypatch.setattr(server_module, "LOCAL_ROLLBACK_APPROVAL_PACKET_PATH", rollback_approval_path)
    monkeypatch.setattr(server_module, "LOCAL_ROLLBACK_EXECUTION_RECEIPT_PATH", rollback_execution_path)
    gate = build_software_dev_capability_admission_gate(clock=_clock)
    app = create_gateway_app(
        platform=StubPlatform(),
        capability_admission_gate_override=gate,
    )
    client = TestClient(app)

    response = client.get(
        "/operator/control-tower"
        "?domain=software_dev&include_local_sandbox_receipts=true"
    )

    assert response.status_code == 200
    assert "Local sandbox bundle" in response.text
    assert "Sandbox Receipt Attachments" in response.text
    assert "Local Sandbox Proof Report" in response.text
    assert "Local Rollback Summary" in response.text
    assert "Local Rollback Approval" in response.text
    assert "Local Rollback Flow Command" in response.text
    assert "Local Rollback Execution Receipt" in response.text
    assert "rollback_ready; 10 artifacts" in response.text
    assert "awaiting_operator_approval; pending" in response.text
    assert "false; 0 selected" in response.text
    assert "blocked_no_approval; dry_run" in response.text
    assert "run_developer_workflow_local_rollback_flow.py" in response.text
    assert "Run local rollback dry-run" in response.text
    assert "developer_workflow_local_rollback_execution_receipt.generated.json" in response.text
    assert "/operator/control-tower/local-rollback-receipt?receipt_id=summary" in response.text
    assert "/operator/control-tower/local-rollback-receipt?receipt_id=approval" in response.text
    assert "/operator/control-tower/local-rollback-receipt?receipt_id=execution" in response.text
    assert "Summary availability" in response.text
    assert "Readiness verdict" in response.text
    assert "awaiting_selection" in response.text
    assert "3/3" in response.text
    assert "--artifact-id &lt;artifact_id&gt;" in response.text
    assert "Remove-Item -LiteralPath" in response.text
    assert "sandbox_receipt_attachment_packet" in response.text
    assert "awaiting_attachments; 1/4 attached" in response.text
    assert "attached; ok true" in response.text
    assert "Local Sandbox Bundle Receipts" in response.text
    assert "Sandbox patch receipt" in response.text
    assert "proof://developer-workflow-v1/sandbox-patch/collected" in response.text
    assert "awaiting_receipts; 1/4 bundle receipts" in response.text
    assert "1/6 required complete" in response.text
    assert "PR Readiness Bundle" in response.text
    assert "First blocker" in response.text


def test_operator_control_tower_local_rollback_receipt_viewer_reads_whitelisted_receipts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "developer_workflow_local_sandbox_proof_report.generated.json"
    report_path.write_text(json.dumps(_local_sandbox_proof_report(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rollback_path = tmp_path / "developer_workflow_local_rollback_summary_packet.generated.json"
    rollback_path.write_text(
        json.dumps(_local_rollback_summary_packet(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    rollback_approval_path = tmp_path / "developer_workflow_local_rollback_approval_packet.generated.json"
    rollback_approval_path.write_text(
        json.dumps(_local_rollback_approval_packet(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    rollback_execution_path = tmp_path / "developer_workflow_local_rollback_execution_receipt.generated.json"
    rollback_execution_path.write_text(
        json.dumps(_local_rollback_execution_receipt(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(server_module, "LOCAL_SANDBOX_PROOF_REPORT_PATH", report_path)
    monkeypatch.setattr(server_module, "LOCAL_ROLLBACK_SUMMARY_PACKET_PATH", rollback_path)
    monkeypatch.setattr(server_module, "LOCAL_ROLLBACK_APPROVAL_PACKET_PATH", rollback_approval_path)
    monkeypatch.setattr(server_module, "LOCAL_ROLLBACK_EXECUTION_RECEIPT_PATH", rollback_execution_path)
    app = create_gateway_app(
        platform=StubPlatform(),
        capability_admission_gate_override=build_software_dev_capability_admission_gate(clock=_clock),
    )
    client = TestClient(app)

    read_model_response = client.get(
        "/operator/control-tower/local-rollback-receipt/read-model?receipt_id=execution"
    )
    html_response = client.get("/operator/control-tower/local-rollback-receipt?receipt_id=approval")
    unknown_response = client.get("/operator/control-tower/local-rollback-receipt/read-model?receipt_id=outside")

    assert read_model_response.status_code == 200
    read_model = read_model_response.json()
    assert read_model["receipt_id"] == "execution"
    assert read_model["label"] == "Local rollback execution receipt"
    assert read_model["projection_only"] is True
    assert read_model["external_effects_allowed"] is False
    assert read_model["path"].endswith("developer_workflow_local_rollback_execution_receipt.generated.json")
    assert read_model["payload"]["receipt_id"] == "developer_workflow_local_rollback_execution_receipt.v1"
    assert len(read_model["payload_hash"]) == 64
    assert html_response.status_code == 200
    assert "Local rollback approval packet" in html_response.text
    assert "Projection only: true" in html_response.text
    assert "developer_workflow_local_rollback_approval_packet.v1" in html_response.text
    assert unknown_response.status_code == 404


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
    assert "/operator/control-tower/status-receipt" in response.text
    assert "/operator/control-tower/developer-workflow-status/read-model" in response.text
    assert "/operator/control-tower?include_developer_workflow_operator_receipt=true" in response.text
    assert "Control Tower Headline" in response.text
    assert "Control tower headline: local lab can continue" in response.text
    assert "Local Lab Readiness" in response.text
    assert "Local lab readiness awaiting evidence" in response.text
    assert "Local Resume Plan" in response.text
    assert "Resume plan: continue local lab in fast mode" in response.text
    assert "Workflow Monitor Summary" in response.text
    assert "Operator Action Card" in response.text
    assert "Next Action Summary" in response.text
    assert "Next action complete sandbox patch, test, diff, and terminal receipts" in response.text
    assert "Approval Readiness Summary" in response.text
    assert "Approval pending; sandbox_receipts_incomplete remains current blocker" in response.text
    assert "Operator Decision Summary" in response.text
    assert "Decision collect_sandbox_receipts can continue in local lab" in response.text
    assert "Friction Reduction Summary" in response.text
    assert "Friction reduced to collect_sandbox_receipts" in response.text
    assert "Developer Workflow Operator Receipt" in response.text
    assert "reload with generated receipt" in response.text
    assert "Action needed before PR execution:" in response.text
    assert "External approval:" in response.text
    assert "Local candidate ready:" in response.text
    assert "PR tool admitted:" in response.text
    assert "External effects allowed: false" in response.text
    assert "Safe Automatic Action Candidates" in response.text
    assert "Safe Local Action Queue" in response.text
    assert "7 safe local actions queued for fast mode" in response.text
    assert "safe_local_action_queue.control_summary.v1" in response.text
    assert "Control level</strong>L3 -> L4" in response.text
    assert "Control next unlock</strong>none" in response.text
    assert "Prepare documentation update" in response.text
    assert "Prepare documentation update in local sandbox" in response.text
    assert "Dangerous Zone Blockers" in response.text
    assert "dangerous real-world zones blocked" in response.text
    assert "dangerous_action_blocker.control_summary.v1" in response.text
    assert "Control level</strong>L0 -> L9" in response.text
    assert "Control next unlock</strong>approval" in response.text
    assert "approval, rollback, and effect receipt required before execution" in response.text
    assert "dangerous_zone_requires_explicit_approval" in response.text
    assert "high, real-world boundary" in response.text
    assert "Lab vs Real-world Summary" in response.text
    assert "Lab mode can prepare 7 local candidates" in response.text
    assert "lab_real_world.control_summary.v1" in response.text
    assert "Real-world write status" in response.text
    assert "Approval Boundary Summary" in response.text
    assert "approval_boundary.control_summary.v1" in response.text
    assert "PR approval required" in response.text
    assert "before_pr_or_real_world_effect" in response.text
    assert "Rollback Control Summary" in response.text
    assert "rollback execution remains receipt-bound" in response.text
    assert "If Mullu can change it, Mullu must also know how to undo it." in response.text
    assert "Capability Registry Summary" in response.text
    assert "capability_registry.control_summary.v1" in response.text
    assert "capabilities preflight-ready" in response.text
    assert "Next blocked capability" in response.text
    assert "Friction Mode Summary" in response.text
    assert "Recommended mode" in response.text
    assert "fast mode recommended for local lab" in response.text
    assert "Safe vs Dangerous Summary" in response.text
    assert "7 local-lab candidates available; 7 real-world zones blocked pending explicit approval" in response.text
    assert "safe_vs_dangerous.control_summary.v1" in response.text
    assert "Unlock Readiness Summary" in response.text
    assert "pending unlocks; next evidence" in response.text
    assert "unlock_readiness.control_summary.v1" in response.text
    assert "Approval blockers" in response.text
    assert "Control System Summary" in response.text
    assert "Control system in fast mode" in response.text
    assert "control_system.control_summary.v1" in response.text
    assert "Next developer workflow action" in response.text
    assert "Developer Workflow Milestone" in response.text
    assert "collect_sandbox_receipts" in response.text
    assert "Developer Workflow Completion" in response.text
    assert "Developer Workflow completion 0/7 evidence receipts" in response.text
    assert "Operator Terminal Closure" in response.text
    assert "Terminal closure AwaitingEvidence" in response.text
    assert "Operator Resume Checkpoint" in response.text
    assert "Resume checkpoint ready for local lab" in response.text
    assert "Operator Sandbox Milestone" in response.text
    assert "Sandbox milestone awaiting receipts" in response.text
    assert "sandbox_patch_receipt, sandbox_test_receipt, sandbox_diff_receipt" in response.text
    assert "Operator Sandbox Receipt Checklist" in response.text
    assert "Sandbox checklist incomplete" in response.text
    assert "Terminal review allowed" in response.text
    assert "Operator Sandbox Patch Receipt" in response.text
    assert "Sandbox patch receipt awaiting attachment" in response.text
    assert "before_state, after_state, diff, command, rollback_command, evidence_ref" in response.text
    assert "Operator Sandbox Patch Command" in response.text
    assert "Sandbox patch command preview ready" in response.text
    assert "collect_developer_workflow_sandbox_receipt_evidence.py" in response.text
    assert "Operator Sandbox Patch Bundle Preview" in response.text
    assert "Sandbox patch bundle preview ready" in response.text
    assert "validate_developer_workflow_sandbox_receipt_bundle.py" in response.text
    assert "Operator Sandbox Patch Readiness Summary" in response.text
    assert "operator_sandbox_patch_validation_readiness_summary" in response.text
    assert "Next evidence" in response.text
    assert "sandbox_patch_receipt_bundle_generated" in response.text
    assert "Operator Sandbox Patch Validation Readiness" in response.text
    assert "Sandbox patch validation blocked until the collected bundle exists" in response.text
    assert "blocked_missing_bundle" in response.text
    assert "Operator Sandbox Patch Terminal Review" in response.text
    assert "Sandbox patch terminal review blocked until bundle generation" in response.text
    assert "blocked_until_validation" in response.text
    assert "Operator Sandbox Patch Approval Readiness" in response.text
    assert "Sandbox patch approval blocked until terminal review closes" in response.text
    assert "blocked_until_terminal_review" in response.text
    assert "Operator Sandbox Patch PR Preparation Readiness" in response.text
    assert "PR preparation blocked until sandbox patch approval is recorded" in response.text
    assert "blocked_until_approval" in response.text
    assert "Operator Sandbox Patch PR Creation Readiness" in response.text
    assert "PR creation blocked until local PR preparation" in response.text
    assert "blocked_until_pr_preparation" in response.text
    assert "Operator Sandbox Patch PR CI Readiness" in response.text
    assert "PR CI readiness blocked until PR creation evidence" in response.text
    assert "blocked_until_pr_creation" in response.text
    assert "Operator Sandbox Patch Merge Readiness" in response.text
    assert "Merge readiness blocked until CI pass" in response.text
    assert "blocked_until_ci_pass" in response.text
    assert "Operator Sandbox Patch Release Handoff Readiness" in response.text
    assert "Release handoff blocked until terminal closure" in response.text
    assert "blocked_until_terminal_closure" in response.text
    assert "Operator Sandbox Patch Deployment Publication Readiness" in response.text
    assert "Deployment publication blocked until release handoff" in response.text
    assert "blocked_until_release_handoff" in response.text
    assert "Operator Sandbox Patch Production Monitoring Readiness" in response.text
    assert "Production monitoring blocked until deployment publication" in response.text
    assert "blocked_until_publication" in response.text
    assert "Operator Sandbox Patch Incident Response Readiness" in response.text
    assert "Incident response blocked until monitoring" in response.text
    assert "blocked_until_monitoring" in response.text
    assert "Operator Sandbox Patch Recovery Closure Readiness" in response.text
    assert "Recovery closure blocked until containment" in response.text
    assert "blocked_until_incident_response" in response.text
    assert "Operator Sandbox Patch Trust Ledger Readiness" in response.text
    assert "Trust ledger anchoring blocked until recovery closure" in response.text
    assert "blocked_until_recovery_closure" in response.text
    assert "Operator Sandbox Patch Terminal Audit Export Readiness" in response.text
    assert "Terminal audit export blocked until trust ledger anchor" in response.text
    assert "blocked_until_trust_ledger_anchor" in response.text
    assert "Operator Sandbox Patch Foundation Closure Readiness" in response.text
    assert "Foundation closure blocked until terminal audit export" in response.text
    assert "blocked_until_terminal_audit_export" in response.text
    assert "Operator Sandbox Patch Iteration Resume Readiness" in response.text
    assert "Iteration resume blocked until foundation closure" in response.text
    assert "blocked_until_foundation_closure" in response.text
    assert "Operator Sandbox Patch Next Scope Admission Readiness" in response.text
    assert "Next scope admission blocked until intake" in response.text
    assert "blocked_until_iteration_resume" in response.text
    assert "Operator Handoff Summary" in response.text
    assert "Handoff ready for local resume" in response.text
    assert "external_pr_creation, branch_push, merge, deployment, connector_write, real_world_effect" in response.text
    assert "Operator Review Readiness" in response.text
    assert "Review readiness awaiting evidence" in response.text
    assert "complete local evidence receipts before review" in response.text
    assert "Operator Review Packet" in response.text
    assert "Review packet awaiting evidence" in response.text
    assert "Operator Blocker Summary" in response.text
    assert "Blocker sandbox_receipts_incomplete is local_evidence" in response.text
    assert "Operator Packet Summary" in response.text
    assert "Packet summary awaiting sandbox_patch_receipt" in response.text
    assert "Operator Authority Summary" in response.text
    assert "Authority local_lab_only; local preparation allowed" in response.text
    assert "Operator Risk Summary" in response.text
    assert "Risk is low because execution is local-lab only" in response.text
    assert "Operator Approval Packet" in response.text
    assert "Approval packet awaiting evidence" in response.text
    assert "Operator Evidence Gap" in response.text
    assert "Evidence gap: 7 of 7 receipts still pending" in response.text
    assert "Operator Rollback Gap" in response.text
    assert "Rollback gap: 0/3 rollback receipts available" in response.text
    assert "Operator PR Gap" in response.text
    assert "PR gap: awaiting_sandbox_receipts; first blocker sandbox_receipts" in response.text
    assert "Operator Dashboard Summary" in response.text
    assert "Dashboard summary: collect_sandbox_receipts" in response.text
    assert "/operator/control-tower/status-receipt?focus_id=sandbox_patch_receipt" in response.text
    assert "sandbox_receipts_incomplete" in response.text
    assert "Monitor status" in response.text
    assert "monitoring" in response.text
    assert "Current task" in response.text
    assert "sandbox_change" in response.text
    assert "Plan review count" in response.text
    assert "External effects allowed" in response.text
    assert "false" in response.text
    assert "Developer Workflow" in response.text
    assert "Mullu Developer Workflow v1" in response.text
    assert "preflight_ready" in response.text
    assert "low, local lab only" in response.text
    assert "Safe automatic zones" in response.text
    assert "write_docs" in response.text
    assert "Dangerous zones" in response.text
    assert "deploy" in response.text
    assert "Rollback default" in response.text
    assert "Rollback receipt" in response.text
    assert "Rollback flow command" in response.text
    assert "Rollback next action" in response.text
    assert "Evidence Progress Summary" in response.text
    assert "0/7 local evidence receipts complete; next sandbox_patch_receipt" in response.text
    assert "Local Rollback Flow Command" in response.text
    assert "run_developer_workflow_local_rollback_flow.py" in response.text
    assert "not_recorded" in response.text
    assert "Local sandbox bundle" in response.text
    assert "not_attached; 0/4 bundle receipts" in response.text
    assert "PR readiness" in response.text
    assert "PR Readiness Bundle" in response.text
    assert "Next Unlock Queue" in response.text
    assert "software_dev.pr_candidate.prepare" in response.text
    assert "approval" in response.text
    assert "Capability Passports" in response.text
    assert "software_dev.change.run" in response.text
    assert "allowed_lab" in response.text
    assert "Mode Selector" in response.text
    assert "Strict" in response.text
    assert "Balanced" in response.text
    assert "Fast" in response.text
    assert "Fast allowed" in response.text
    assert "Receipt Checklist" in response.text
    assert "Sandbox patch receipt" in response.text
    assert "Operator approval" in response.text
    assert "Sandbox-to-PR Readiness" in response.text
    assert "awaiting_receipts" in response.text
    assert "complete sandbox patch, test, diff, and terminal receipts" in response.text
    assert "Sandbox-to-PR Packet" in response.text
    assert "Sandbox attachments" in response.text
    assert "Local proof report" in response.text
    assert "Local Sandbox Proof Report" in response.text
    assert "Next attachment" in response.text
    assert "Sandbox Receipt Attachments" in response.text
    assert "Next evidence focus" in response.text
    assert "Focus" in response.text
    assert "Next evidence" in response.text
    assert "PR packet" in response.text
    assert "sandbox_receipts_incomplete" in response.text
    assert "capability_passports" in response.text
    assert "Test gate receipt" in response.text
    assert "Diff review receipt" in response.text
    assert "Terminal receipt" in response.text
    assert "review diff receipt before approving pull request candidate" in response.text
    assert "/operator/capabilities/friction-control/read-model?domain=software_dev" in response.text
    assert "/operator/developer-workflow" in response.text
    assert "/operator/developer-workflow/read-model" in response.text
    assert "sandbox_change" in response.text
    assert "/operator/current-task" in response.text
    assert "/operator/plan-review" in response.text
    assert "/operator/approvals" in response.text
    assert "/operator/receipts" in response.text


def test_sandbox_patch_readiness_registry_preserves_no_effect_contract() -> None:
    registry_keys = [summary_key for summary_key, _payload, _source_ref in SANDBOX_PATCH_READINESS_REGISTRY]
    entries = sandbox_patch_readiness_receipt_entries()
    source_refs = sandbox_patch_readiness_source_refs()
    compact_summary = sandbox_patch_readiness_compact_summary()

    assert registry_keys[0] == "operator_sandbox_patch_validation_readiness_summary"
    assert registry_keys[-1] == "operator_sandbox_patch_next_scope_admission_readiness_summary"
    assert len(registry_keys) == len(set(registry_keys)) == len(entries) == len(source_refs)
    assert compact_summary["blocked_stage_summary_key"] == registry_keys[0]
    assert compact_summary["blocked_stage_status"] == "blocked_missing_bundle"
    assert compact_summary["next_evidence_id"] == "sandbox_patch_receipt_bundle_generated"
    assert compact_summary["missing_prerequisite_count"] == 2
    assert compact_summary["external_effects_allowed"] is False

    for summary_key, payload, source_ref in SANDBOX_PATCH_READINESS_REGISTRY:
        entry = entries[summary_key]
        required_fields = [value for key, value in entry.items() if key.startswith("required_before_")]
        no_effect_flags = {
            key: value
            for key, value in entry.items()
            if key.endswith("_allowed")
            or key.endswith("_performed")
            or key.endswith("_started")
            or key.endswith("_certified")
            or key.endswith("_admitted")
        }

        assert entry == payload
        assert source_refs[summary_key] == source_ref
        assert source_ref.startswith("docs/21_workflow_runtime.md sandbox_patch_receipt ")
        assert entry["external_effects_allowed"] is False
        assert required_fields and entry["missing_prerequisite_count"] == len(required_fields[0])
        assert no_effect_flags and all(value is False for value in no_effect_flags.values())

    entries[registry_keys[0]]["required_before_validation"].append("mutated")
    fresh_entries = sandbox_patch_readiness_receipt_entries()

    assert "mutated" not in fresh_entries[registry_keys[0]]["required_before_validation"]


def test_operator_control_tower_status_receipt_route_exports_focus() -> None:
    gate = build_software_dev_capability_admission_gate(clock=_clock)
    app = create_gateway_app(
        platform=StubPlatform(),
        capability_admission_gate_override=gate,
    )
    client = TestClient(app)

    response = client.get("/operator/control-tower/status-receipt?domain=software_dev")

    assert response.status_code == 200
    receipt = response.json()
    receipt_schema = json.loads(CONTROL_TOWER_STATUS_RECEIPT_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(receipt_schema).validate(receipt)
    assert receipt["receipt_type"] == "operator_control_tower_status_receipt.v1"
    assert receipt["projection_only"] is True
    assert receipt["external_effects_allowed"] is False
    assert receipt["receipt_id"].startswith("operator-control-tower-status-")
    assert len(receipt["receipt_hash"]) >= 32
    assert receipt["task"] == "Mullu Developer Workflow v1"
    assert receipt["status"] == "preflight_ready"
    assert receipt["workflow_monitor_summary"]["monitor_status"] == "monitoring"
    assert receipt["workflow_monitor_summary"]["current_task_id"] == "sandbox_change"
    assert receipt["workflow_monitor_summary"]["current_task_count"] >= 1
    assert receipt["workflow_monitor_summary"]["plan_review_count"] >= 1
    assert receipt["workflow_monitor_summary"]["blocked_count"] == 0
    assert receipt["workflow_monitor_summary"]["review_count"] == 0
    assert receipt["workflow_monitor_summary"]["workflow_status"] == "waiting_for_approval"
    assert receipt["workflow_monitor_summary"]["readiness_status"] == "awaiting_receipts"
    assert receipt["workflow_monitor_summary"]["blocker"] == "sandbox_receipts_incomplete"
    assert receipt["workflow_monitor_summary"]["next_action"] == (
        "complete sandbox patch, test, diff, and terminal receipts"
    )
    assert receipt["workflow_monitor_summary"]["execution_boundary"] == "local_lab_only"
    assert receipt["workflow_monitor_summary"]["external_effects_allowed"] is False

    assert receipt["operator_action_card"]["card_id"] == "developer_workflow_next_action"
    assert receipt["control_tower_headline_summary"] == {
        "summary_id": "control_tower_headline.foundation",
        "task": "Mullu Developer Workflow v1",
        "status": "preflight_ready",
        "headline_status": "local_lab_ready",
        "current_milestone": "collect_sandbox_receipts",
        "current_blocker": "sandbox_receipts_incomplete",
        "recommended_mode": "fast",
        "safe_local_candidate_count": 7,
        "dangerous_blocker_count": 7,
        "local_continuation_allowed": True,
        "approval_boundary": "before_pr_or_real_world_effect",
        "next_action": "complete sandbox patch, test, diff, and terminal receipts",
        "next_evidence_id": "sandbox_patch_receipt",
        "external_effects_allowed": False,
        "operator_message": (
            "Control tower headline: local lab can continue; "
            "7 safe local candidates; 7 dangerous zones blocked"
        ),
    }
    assert receipt["local_lab_readiness_summary"] == {
        "summary_id": "local_lab_readiness.foundation",
        "readiness_status": "awaiting_evidence",
        "lab_mode_allowed": True,
        "local_continuation_allowed": True,
        "safe_candidate_count": 7,
        "pending_evidence_count": 7,
        "next_evidence_id": "sandbox_patch_receipt",
        "rollback_receipt_available_count": 0,
        "rollback_receipt_required_count": 3,
        "rollback_ready": False,
        "next_action": "complete sandbox patch, test, diff, and terminal receipts",
        "approval_boundary": "before_pr_or_real_world_effect",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "operator_message": (
            "Local lab readiness awaiting evidence; "
            "7 evidence receipts pending; rollback receipts 0/3"
        ),
    }
    assert receipt["local_resume_plan_summary"] == {
        "summary_id": "local_resume_plan.foundation",
        "resume_status": "ready_for_local_continuation",
        "continue_allowed": True,
        "recommended_mode": "fast",
        "current_milestone": "collect_sandbox_receipts",
        "current_blocker": "sandbox_receipts_incomplete",
        "next_action": "complete sandbox patch, test, diff, and terminal receipts",
        "next_evidence_id": "sandbox_patch_receipt",
        "safe_candidate_count": 7,
        "pending_evidence_count": 7,
        "rollback_ready": False,
        "approval_required_now": False,
        "approval_boundary": "before_pr_or_real_world_effect",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "operator_message": (
            "Resume plan: continue local lab in fast mode; "
            "next evidence sandbox_patch_receipt; 7 evidence receipts pending"
        ),
    }
    assert receipt["operator_action_card"]["card_id"] == "developer_workflow_next_action"
    assert receipt["operator_action_card"]["title"] == "Next developer workflow action"
    assert receipt["operator_action_card"]["status"] == "awaiting_receipts"
    assert receipt["operator_action_card"]["reason"] == "sandbox_receipts_incomplete"
    assert receipt["operator_action_card"]["primary_action"] == (
        "complete sandbox patch, test, diff, and terminal receipts"
    )
    assert receipt["operator_action_card"]["primary_href"] == (
        "/operator/control-tower/status-receipt?focus_id=sandbox_patch_receipt"
    )
    assert receipt["operator_action_card"]["focus_id"] == "sandbox_patch_receipt"
    assert receipt["operator_action_card"]["task_id"] == "sandbox_change"
    assert receipt["operator_action_card"]["risk"] == "low, local lab only"
    assert receipt["operator_action_card"]["execution_boundary"] == "local_lab_only"
    assert receipt["operator_action_card"]["approval_required"] is False
    assert receipt["operator_action_card"]["external_effects_allowed"] is False
    assert receipt["next_action_summary"] == {
        "summary_id": "next_action.foundation",
        "status": "awaiting_receipts",
        "reason": "sandbox_receipts_incomplete",
        "primary_action": "complete sandbox patch, test, diff, and terminal receipts",
        "primary_href": "/operator/control-tower/status-receipt?focus_id=sandbox_patch_receipt",
        "focus_id": "sandbox_patch_receipt",
        "focus_label": "Sandbox patch receipt",
        "focus_status": "pending",
        "focus_source": "workflow_monitor.metadata.developer_workflow_run.receipt_checklist.sandbox_patch_receipt",
        "required_evidence": [
            "sandbox_patch_receipt",
            "test_gate_receipt",
            "diff_review_receipt",
            "terminal_receipt",
        ],
        "required_evidence_count": 4,
        "approval_required": False,
        "risk": "low, local lab only",
        "operator_message": (
            "Next action complete sandbox patch, test, diff, and terminal receipts; "
            "focus sandbox_patch_receipt"
        ),
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }
    assert receipt["approval_readiness_summary"] == {
        "summary_id": "approval_readiness.foundation",
        "approval_required": True,
        "operator_approval_status": "pending",
        "approval_missing": True,
        "current_blocker": "sandbox_receipts_incomplete",
        "approval_boundary": "before_pr_or_real_world_effect",
        "next_approval_action": "complete sandbox receipts before requesting approval",
        "approval_target_href": "/operator/control-tower/status-receipt?focus_id=sandbox_patch_receipt",
        "pr_candidate_status": "pending",
        "ready_for_pr_candidate_preparation": False,
        "external_pr_execution_allowed": False,
        "operator_message": "Approval pending; sandbox_receipts_incomplete remains current blocker",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }
    assert receipt["operator_decision_summary"] == {
        "summary_id": "operator_decision.foundation",
        "decision_status": "awaiting_receipts",
        "decision_kind": "evidence_collection",
        "current_milestone": "collect_sandbox_receipts",
        "current_blocker": "sandbox_receipts_incomplete",
        "recommended_action": "complete sandbox patch, test, diff, and terminal receipts",
        "action_href": "/operator/control-tower/status-receipt?focus_id=sandbox_patch_receipt",
        "next_evidence_id": "sandbox_patch_receipt",
        "operator_review_required_now": False,
        "operator_review_required_before_external_effect": True,
        "approval_status": "pending",
        "local_continuation_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "operator_message": (
            "Decision collect_sandbox_receipts can continue in local lab; "
            "approval pending before PR or real-world effect"
        ),
    }
    assert receipt["friction_reduction_summary"] == {
        "summary_id": "friction_reduction.foundation",
        "reduction_status": "local_continuation_ready",
        "current_milestone": "collect_sandbox_receipts",
        "current_blocker": "sandbox_receipts_incomplete",
        "local_continuation_allowed": True,
        "pending_evidence_count": 7,
        "next_evidence_id": "sandbox_patch_receipt",
        "approval_boundary": "before_pr_or_real_world_effect",
        "operator_review_required_now": False,
        "external_effects_allowed": False,
        "operator_message": (
            "Friction reduced to collect_sandbox_receipts; continue local evidence collection, "
            "while PR and real-world effects remain approval-bound"
        ),
    }
    assert receipt["safe_local_action_queue_summary"] == {
        "summary_id": "safe_local_action_queue.foundation",
        "queue_status": "ready",
        "candidate_count": 7,
        "first_candidate_id": "safe_zone.write_docs",
        "first_zone": "write_docs",
        "first_action": "Prepare documentation update in local sandbox",
        "recommended_mode": "fast",
        "approval_required": False,
        "local_execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "operator_message": (
            "7 safe local actions queued for fast mode; "
            "approval not required for local preparation"
        ),
    }
    assert receipt["dangerous_action_blocker_summary"] == {
        "summary_id": "dangerous_action_blocker.foundation",
        "blocker_status": "blocked",
        "blocker_count": 7,
        "first_blocker_id": "dangerous_zone.delete_files",
        "first_zone": "delete_files",
        "first_reason": "dangerous_zone_requires_explicit_approval",
        "required_evidence": [
            "operator_approval",
            "rollback_plan",
            "effect_receipt",
        ],
        "approval_required": True,
        "rollback_required": True,
        "real_world_execution_boundary": "real_world",
        "external_effects_allowed": False,
        "operator_message": (
            "7 dangerous real-world zones blocked; "
            "approval, rollback, and effect receipt required before execution"
        ),
    }
    assert len(receipt["safe_automatic_action_candidates"]) == 7
    receipt_docs_candidate = next(
        item for item in receipt["safe_automatic_action_candidates"] if item["zone"] == "write_docs"
    )
    assert receipt_docs_candidate["candidate_id"] == "safe_zone.write_docs"
    assert receipt_docs_candidate["status"] == "candidate"
    assert receipt_docs_candidate["primary_action"] == "Prepare documentation update in local sandbox"
    assert receipt_docs_candidate["execution_boundary"] == "local_lab_only"
    assert receipt_docs_candidate["approval_required"] is False
    assert receipt_docs_candidate["external_effects_allowed"] is False
    assert len(receipt["dangerous_zone_blockers"]) == 7
    receipt_deploy_blocker = next(
        item for item in receipt["dangerous_zone_blockers"] if item["zone"] == "deploy"
    )
    assert receipt_deploy_blocker["blocker_id"] == "dangerous_zone.deploy"
    assert receipt_deploy_blocker["status"] == "blocked"
    assert receipt_deploy_blocker["reason"] == "dangerous_zone_requires_explicit_approval"
    assert receipt_deploy_blocker["required_evidence"] == [
        "operator_approval",
        "rollback_plan",
        "effect_receipt",
    ]
    assert receipt_deploy_blocker["risk"] == "high, real-world boundary"
    assert receipt_deploy_blocker["execution_boundary"] == "real_world"
    assert receipt_deploy_blocker["approval_required"] is True
    assert receipt_deploy_blocker["external_effects_allowed"] is False
    assert receipt["lab_real_world_summary"]["summary_id"] == "lab_real_world.foundation"
    assert receipt["lab_real_world_summary"]["lab_mode_allowed"] is True
    assert receipt["lab_real_world_summary"]["lab_safe_candidate_count"] == 7
    assert receipt["lab_real_world_summary"]["real_world_effects_allowed"] is False
    assert receipt["lab_real_world_summary"]["dangerous_blocker_count"] == 7
    assert receipt["lab_real_world_summary"]["dangerous_approval_required_count"] == 7
    assert receipt["lab_real_world_summary"]["lab_execution_boundary"] == "local_lab_only"
    assert receipt["lab_real_world_summary"]["real_world_execution_boundary"] == "real_world"
    assert receipt["lab_real_world_summary"]["external_effects_allowed"] is False
    assert receipt["approval_boundary_summary"]["summary_id"] == "approval_boundary.foundation"
    assert receipt["approval_boundary_summary"]["local_auto_candidate_count"] == 7
    assert receipt["approval_boundary_summary"]["approval_unlock_count"] >= 1
    assert receipt["approval_boundary_summary"]["dangerous_approval_required_count"] == 7
    assert receipt["approval_boundary_summary"]["pr_approval_required"] is True
    assert receipt["approval_boundary_summary"]["approval_boundary"] == "before_pr_or_real_world_effect"
    assert receipt["approval_boundary_summary"]["execution_boundary"] == "local_lab_only"
    assert receipt["approval_boundary_summary"]["external_effects_allowed"] is False
    assert receipt["rollback_control_summary"]["summary_id"] == "rollback_control.foundation"
    assert receipt["rollback_control_summary"]["rollback_default_count"] >= 1
    assert receipt["rollback_control_summary"]["rollback_required_count"] >= 1
    assert receipt["rollback_control_summary"]["capability_count"] == 12
    assert receipt["rollback_control_summary"]["rollback_default_ready"] is True
    assert receipt["rollback_control_summary"]["sandbox_to_pr_policy_ready"] is True
    assert "rollback execution remains receipt-bound" in receipt["rollback_control_summary"]["operator_message"]
    assert receipt["rollback_control_summary"]["execution_boundary"] == "local_lab_only"
    assert receipt["rollback_control_summary"]["external_effects_allowed"] is False
    assert receipt["capability_registry_summary"]["summary_id"] == "capability_registry.foundation"
    assert receipt["capability_registry_summary"]["capability_count"] == 12
    assert receipt["capability_registry_summary"]["blocked_count"] >= 1
    assert receipt["capability_registry_summary"]["approval_required_count"] >= 1
    assert receipt["capability_registry_summary"]["pending_unlock_count"] >= 1
    assert receipt["capability_registry_summary"]["next_blocked_reason"] == "approval"
    assert "approval" in receipt["capability_registry_summary"]["next_required_evidence"]
    assert receipt["capability_registry_summary"]["execution_boundary"] == "local_lab_only"
    assert receipt["capability_registry_summary"]["external_effects_allowed"] is False
    assert receipt["friction_mode_summary"]["summary_id"] == "friction_mode.foundation"
    assert receipt["friction_mode_summary"]["default_mode"] == "balanced"
    assert receipt["friction_mode_summary"]["foundation_recommended_mode"] == "fast"
    assert receipt["friction_mode_summary"]["fast_allowed_count"] >= 1
    assert receipt["friction_mode_summary"]["balanced_approval_required_count"] >= 1
    assert "fast mode recommended for local lab" in receipt["friction_mode_summary"]["operator_message"]
    assert receipt["friction_mode_summary"]["execution_boundary"] == "local_lab_only"
    assert receipt["friction_mode_summary"]["external_effects_allowed"] is False
    assert receipt["safe_vs_dangerous_summary"]["summary_id"] == "safe_vs_dangerous.local_lab"
    assert receipt["safe_vs_dangerous_summary"]["safe_candidate_count"] == 7
    assert receipt["safe_vs_dangerous_summary"]["dangerous_blocker_count"] == 7
    assert receipt["safe_vs_dangerous_summary"]["first_safe_zone"] == "write_docs"
    assert receipt["safe_vs_dangerous_summary"]["first_dangerous_zone"] == "delete_files"
    assert receipt["safe_vs_dangerous_summary"]["safe_execution_boundary"] == "local_lab_only"
    assert receipt["safe_vs_dangerous_summary"]["dangerous_execution_boundary"] == "real_world"
    assert receipt["safe_vs_dangerous_summary"]["external_effects_allowed"] is False
    assert receipt["unlock_readiness_summary"]["summary_id"] == "unlock_readiness.local_lab"
    assert receipt["unlock_readiness_summary"]["pending_unlock_count"] >= 1
    assert receipt["unlock_readiness_summary"]["safe_candidate_count"] == 7
    assert receipt["unlock_readiness_summary"]["dangerous_blocker_count"] == 7
    assert receipt["unlock_readiness_summary"]["next_unlock"] == "approval"
    assert "approval" in receipt["unlock_readiness_summary"]["next_required_evidence"]
    assert receipt["unlock_readiness_summary"]["safe_candidates_ready"] == 7
    assert receipt["unlock_readiness_summary"]["dangerous_blockers_requiring_approval"] == 7
    assert receipt["unlock_readiness_summary"]["execution_boundary"] == "local_lab_only"
    assert receipt["unlock_readiness_summary"]["external_effects_allowed"] is False
    assert receipt["control_system_summary"]["summary_id"] == "control_system.foundation"
    assert receipt["control_system_summary"]["task"] == "Mullu Developer Workflow v1"
    assert receipt["control_system_summary"]["status"] == "preflight_ready"
    assert receipt["control_system_summary"]["recommended_mode"] == "fast"
    assert receipt["control_system_summary"]["lab_mode_allowed"] is True
    assert receipt["control_system_summary"]["capability_count"] == 12
    assert receipt["control_system_summary"]["pending_unlock_count"] >= 1
    assert receipt["control_system_summary"]["safe_candidate_count"] == 7
    assert receipt["control_system_summary"]["dangerous_blocker_count"] == 7
    assert receipt["control_system_summary"]["next_unlock"] == "approval"
    assert "approval" in receipt["control_system_summary"]["next_required_evidence"]
    assert receipt["control_system_summary"]["risk"] == "low, local lab only"
    assert receipt["control_system_summary"]["action_needed"] == (
        "review diff receipt before approving pull request candidate"
    )
    assert "Control system in fast mode" in receipt["control_system_summary"]["operator_message"]
    assert receipt["control_system_summary"]["execution_boundary"] == "local_lab_only"
    assert receipt["control_system_summary"]["external_effects_allowed"] is False
    assert receipt["sandbox_to_pr"]["blocker"] == "sandbox_receipts_incomplete"
    assert receipt["sandbox_to_pr"]["focus"]["focus_id"] == "sandbox_patch_receipt"
    assert receipt["sandbox_to_pr"]["focus"]["status"] == "pending"
    assert receipt["sandbox_to_pr"]["focus"]["action"] == (
        "attach before state, after state, diff, command, and rollback receipt"
    )
    assert receipt["sandbox_to_pr_summary"] == {
        "status": "awaiting_receipts",
        "blocker": "sandbox_receipts_incomplete",
        "focus_id": "sandbox_patch_receipt",
        "focus_status": "pending",
        "next_action": "complete sandbox patch, test, diff, and terminal receipts",
        "next_evidence_count": 4,
        "receipt_completed_count": 0,
        "receipt_required_count": 4,
        "operator_approval_status": "pending",
        "pr_candidate_status": "pending",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }
    assert receipt["sandbox_receipt_attachments"]["packet_id"] == (
        "developer_workflow_sandbox_receipt_attachment_packet.v1"
    )
    assert receipt["sandbox_receipt_attachments"]["packet_status"] == "awaiting_attachments"
    assert receipt["sandbox_receipt_attachments"]["external_effects_allowed"] is False
    assert receipt["sandbox_receipt_attachments"]["next_attachment"]["receipt_id"] == "sandbox_patch_receipt"
    assert receipt["sandbox_receipt_attachments"]["attachments"][0]["receipt_id"] == "sandbox_patch_receipt"
    assert receipt["sandbox_receipt_bundle_summary"] == {
        "status": "not_attached",
        "completed_count": 0,
        "required_count": 0,
        "receipt_count": 0,
        "next_receipt_id": "sandbox_patch_receipt",
        "next_receipt_status": "pending",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }
    assert receipt["sandbox_receipt_attachment_readiness_summary"] == {
        "packet_status": "awaiting_attachments",
        "completed_count": 0,
        "required_count": 4,
        "next_receipt_id": "sandbox_patch_receipt",
        "next_label": "Sandbox patch receipt",
        "next_status": "awaiting_attachment",
        "next_action": "attach before state, after state, diff, command, and rollback receipt",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }
    assert receipt["local_sandbox_proof_report"]["status"] == "not_attached"
    assert receipt["local_sandbox_proof_report"]["external_effects_allowed"] is False
    assert receipt["local_sandbox_proof_report"]["execution_performed"] is False
    assert receipt["local_sandbox_proof_readiness_summary"] == {
        "proof_status": "not_attached",
        "ok": False,
        "bundle_status": "unknown",
        "attachment_packet_status": "unknown",
        "next_attachment_id": "unknown",
        "pr_readiness_status": "unknown",
        "completed_count": 0,
        "required_count": 0,
        "execution_performed": False,
        "external_effects_allowed": False,
    }
    assert receipt["local_rollback_summary_packet"]["status"] == "not_attached"
    assert receipt["local_rollback_summary_packet"]["packet_status"] == "rollback_unavailable"
    assert receipt["local_rollback_summary_packet"]["rollback_execution_performed"] is False
    assert receipt["local_rollback_summary_packet"]["external_effects_allowed"] is False
    assert receipt["local_rollback_approval_packet"]["status"] == "not_attached"
    assert receipt["local_rollback_approval_packet"]["packet_status"] == "awaiting_operator_approval"
    assert receipt["local_rollback_approval_packet"]["approval_status"] == "pending"
    assert receipt["local_rollback_approval_packet"]["delete_execution_allowed"] is False
    assert receipt["local_rollback_approval_packet"]["rollback_execution_performed"] is False
    assert receipt["local_rollback_approval_packet"]["external_effects_allowed"] is False
    assert receipt["local_rollback_execution_receipt"]["status"] == "not_attached"
    assert receipt["local_rollback_execution_receipt"]["execution_status"] == "blocked_no_approval"
    assert receipt["local_rollback_execution_receipt"]["execution_mode"] == "dry_run"
    assert receipt["local_rollback_execution_receipt"]["rollback_execution_performed"] is False
    assert receipt["local_rollback_execution_receipt"]["external_effects_allowed"] is False
    assert receipt["local_rollback_receipts_summary"] == {
        "summary_status": "not_attached",
        "approval_status": "pending",
        "execution_status": "blocked_no_approval",
        "execution_mode": "dry_run",
        "generated_artifact_count": 0,
        "selected_artifact_count": 0,
        "attached_receipt_count": 0,
        "required_receipt_count": 3,
        "delete_execution_allowed": False,
        "rollback_execution_performed": False,
        "external_effects_allowed": False,
    }
    assert receipt["local_rollback_flow_command"]["status"] == "awaiting_selection"
    assert receipt["local_rollback_flow_command"]["action_label"] == "Run local rollback dry-run"
    assert receipt["local_rollback_flow_command"]["next_action"] == (
        "select at least one generated artifact before running rollback flow"
    )
    assert receipt["local_rollback_flow_command"]["selected_artifact_ids"] == []
    assert receipt["local_rollback_flow_command"]["rollback_summary_path"].endswith(
        "developer_workflow_local_rollback_summary_packet.generated.json"
    )
    assert receipt["local_rollback_flow_command"]["approval_packet_path"].endswith(
        "developer_workflow_local_rollback_approval_packet.generated.json"
    )
    assert receipt["local_rollback_flow_command"]["dry_run_receipt_path"].endswith(
        "developer_workflow_local_rollback_execution_receipt.generated.json"
    )
    assert receipt["local_rollback_flow_command"]["execution_receipt_path"].endswith(
        "developer_workflow_local_rollback_execution_receipt.generated.json"
    )
    assert receipt["local_rollback_flow_command"]["rollback_summary_href"].endswith("receipt_id=summary")
    assert receipt["local_rollback_flow_command"]["approval_packet_href"].endswith("receipt_id=approval")
    assert receipt["local_rollback_flow_command"]["dry_run_receipt_href"].endswith("receipt_id=execution")
    assert receipt["local_rollback_flow_command"]["execution_receipt_href"].endswith("receipt_id=execution")
    assert receipt["local_rollback_flow_command"]["receipt_availability"] == {
        "summary": "unavailable",
        "approval": "unavailable",
        "execution": "unavailable",
        "available_count": 0,
        "required_count": 3,
    }
    assert receipt["local_rollback_flow_command"]["readiness_verdict"] == "awaiting_selection"
    assert "run_developer_workflow_local_rollback_flow.py" in receipt["local_rollback_flow_command"]["command"]
    assert "--artifact-id <artifact_id>" in receipt["local_rollback_flow_command"]["command"]
    assert "--execute" not in receipt["local_rollback_flow_command"]["command"]
    assert receipt["local_rollback_flow_command"]["execute_command"].endswith("--json --execute")
    assert receipt["local_rollback_flow_command"]["dry_run_required"] is True
    assert receipt["local_rollback_flow_command"]["execution_requires_execute_flag"] is True
    assert receipt["local_rollback_flow_command"]["external_effects_allowed"] is False
    assert receipt["local_rollback_flow_readiness_summary"] == {
        "readiness_verdict": "awaiting_selection",
        "command_status": "awaiting_selection",
        "selected_artifact_count": 0,
        "receipt_available_count": 0,
        "receipt_required_count": 3,
        "next_action": "select at least one generated artifact before running rollback flow",
        "dry_run_required": True,
        "execution_requires_execute_flag": True,
        "external_effects_allowed": False,
    }
    assert receipt["pr_readiness"]["readiness_status"] == "awaiting_sandbox_receipts"
    assert receipt["pr_readiness"]["first_blocker"] == "sandbox_receipts"
    assert receipt["pr_readiness"]["ready_for_external_pr_execution"] is False
    assert receipt["pr_readiness_summary"] == {
        "readiness_status": "awaiting_sandbox_receipts",
        "ready_for_external_pr_execution": False,
        "first_blocker": "sandbox_receipts",
        "next_evidence_count": 7,
        "receipt_completed_count": 0,
        "receipt_required_count": 4,
        "preview_only": True,
        "execution_performed": False,
        "external_effects_allowed": False,
        "pr_creation_allowed": False,
        "branch_push_allowed": False,
    }
    assert receipt["evidence_progress_summary"] == {
        "summary_id": "evidence_progress.foundation",
        "status": "awaiting_evidence",
        "completed_count": 0,
        "required_count": 7,
        "pending_count": 7,
        "next_evidence_id": "sandbox_patch_receipt",
        "next_action": "attach before state, after state, diff, command, and rollback receipt",
        "blocker": "sandbox_receipts_incomplete",
        "sandbox_receipt_completed_count": 0,
        "sandbox_receipt_required_count": 4,
        "sandbox_bundle_completed_count": 0,
        "sandbox_bundle_required_count": 0,
        "rollback_receipt_available_count": 0,
        "rollback_receipt_required_count": 3,
        "pr_next_evidence_count": 7,
        "operator_message": "0/7 local evidence receipts complete; next sandbox_patch_receipt",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }
    assert receipt["developer_workflow_operator_receipt_summary"] == {
        "solver_outcome": "AwaitingEvidence",
        "readiness_status": "awaiting_sandbox_receipts",
        "ready_for_external_pr_execution": False,
        "command_preview_rendered": False,
        "next_evidence_count": 7,
        "execution_performed": False,
        "external_effects_allowed": False,
    }
    assert receipt["developer_workflow_readiness_summary"] == {
        "workflow_status": "waiting_for_approval",
        "current_task_id": "sandbox_change",
        "readiness_status": "awaiting_receipts",
        "packet_status": "awaiting_receipts",
        "blocker": "sandbox_receipts_incomplete",
        "receipt_completed_count": 0,
        "receipt_required_count": 4,
        "checklist_completed_required_count": 0,
        "checklist_required_count": 6,
        "operator_approval_status": "pending",
        "pr_candidate_status": "pending",
        "rollback_receipt_status": "not_recorded",
        "next_action": "complete sandbox patch, test, diff, and terminal receipts",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }
    assert receipt["developer_workflow_milestone_summary"] == {
        "summary_id": "developer_workflow_milestone.foundation",
        "workflow_status": "waiting_for_approval",
        "readiness_status": "awaiting_receipts",
        "current_task_id": "sandbox_change",
        "current_milestone": "collect_sandbox_receipts",
        "blocker": "sandbox_receipts_incomplete",
        "next_action": "complete sandbox patch, test, diff, and terminal receipts",
        "receipt_completed_count": 0,
        "receipt_required_count": 4,
        "operator_approval_status": "pending",
        "pr_candidate_status": "pending",
        "operator_message": (
            "Developer workflow milestone collect_sandbox_receipts; next action "
            "complete sandbox patch, test, diff, and terminal receipts"
        ),
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }
    assert receipt["developer_workflow_completion_summary"] == {
        "summary_id": "developer_workflow_completion.foundation",
        "workflow_status": "waiting_for_approval",
        "completion_status": "awaiting_evidence",
        "current_milestone": "collect_sandbox_receipts",
        "current_blocker": "sandbox_receipts_incomplete",
        "completed_evidence_count": 0,
        "required_evidence_count": 7,
        "pending_evidence_count": 7,
        "progress_percent": 0,
        "next_closure_condition": "complete local evidence receipts before approval",
        "terminal_closure_ready": False,
        "pr_creation_allowed": False,
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "operator_message": (
            "Developer Workflow completion 0/7 evidence receipts; "
            "next closure condition complete local evidence receipts before approval"
        ),
    }
    assert receipt["operator_terminal_closure_summary"] == {
        "summary_id": "operator_terminal_closure.foundation",
        "terminal_status": "AwaitingEvidence",
        "closure_ready": False,
        "workflow_status": "waiting_for_approval",
        "completion_status": "awaiting_evidence",
        "current_blocker": "sandbox_receipts_incomplete",
        "pending_evidence_count": 7,
        "review_ready": False,
        "approval_status": "pending",
        "rollback_ready": False,
        "pr_creation_allowed": False,
        "branch_push_allowed": False,
        "next_closure_condition": "complete local evidence receipts before approval",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "operator_message": "Terminal closure AwaitingEvidence; 7 evidence receipts pending",
    }
    assert receipt["operator_resume_checkpoint_summary"] == {
        "summary_id": "operator_resume_checkpoint.foundation",
        "checkpoint_status": "ready_for_local_resume",
        "resume_allowed": True,
        "terminal_status": "AwaitingEvidence",
        "recommended_mode": "fast",
        "current_milestone": "collect_sandbox_receipts",
        "current_blocker": "sandbox_receipts_incomplete",
        "next_action": "complete sandbox patch, test, diff, and terminal receipts",
        "next_evidence_id": "sandbox_patch_receipt",
        "pending_evidence_count": 7,
        "rollback_ready": False,
        "approval_required_now": False,
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "operator_message": (
            "Resume checkpoint ready for local lab; next evidence sandbox_patch_receipt; "
            "7 evidence receipts pending"
        ),
    }
    assert receipt["operator_sandbox_milestone_summary"] == {
        "summary_id": "operator_sandbox_milestone.foundation",
        "milestone_status": "awaiting_receipts",
        "milestone": "collect_sandbox_receipts",
        "next_evidence_id": "sandbox_patch_receipt",
        "next_action": "attach before state, after state, diff, command, and rollback receipt",
        "completed_evidence_count": 0,
        "required_evidence_count": 7,
        "pending_evidence_count": 7,
        "required_receipts": [
            "sandbox_patch_receipt",
            "sandbox_test_receipt",
            "sandbox_diff_receipt",
            "dry_run_receipt",
            "rollback_plan_receipt",
            "terminal_review_receipt",
            "operator_approval_packet_receipt",
        ],
        "write_authority_granted": False,
        "pr_creation_allowed": False,
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "operator_message": (
            "Sandbox milestone awaiting receipts; next evidence sandbox_patch_receipt; "
            "7 evidence receipts pending"
        ),
    }
    assert receipt["operator_sandbox_receipt_checklist_summary"] == {
        "summary_id": "operator_sandbox_receipt_checklist.foundation",
        "checklist_status": "incomplete",
        "next_receipt_id": "sandbox_patch_receipt",
        "next_receipt_action": "attach before state, after state, diff, command, and rollback receipt",
        "completed_receipt_count": 0,
        "required_receipt_count": 7,
        "pending_receipt_count": 7,
        "receipt_sequence": [
            "sandbox_patch_receipt",
            "sandbox_test_receipt",
            "sandbox_diff_receipt",
            "dry_run_receipt",
            "rollback_plan_receipt",
            "terminal_review_receipt",
            "operator_approval_packet_receipt",
        ],
        "terminal_review_allowed": False,
        "write_authority_granted": False,
        "external_effects_allowed": False,
        "operator_message": "Sandbox checklist incomplete; next receipt sandbox_patch_receipt; 7 receipts pending",
    }
    assert receipt["operator_sandbox_patch_receipt_summary"] == {
        "summary_id": "operator_sandbox_patch_receipt.foundation",
        "receipt_id": "sandbox_patch_receipt",
        "receipt_status": "awaiting_attachment",
        "required_parts": [
            "before_state",
            "after_state",
            "diff",
            "command",
            "rollback_command",
            "evidence_ref",
        ],
        "next_action": "attach before state, after state, diff, command, and rollback receipt",
        "rollback_required": True,
        "dry_run_required": True,
        "write_authority_granted": False,
        "attachment_allowed": False,
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "operator_message": (
            "Sandbox patch receipt awaiting attachment; required parts before_state, "
            "after_state, diff, command, rollback_command, evidence_ref"
        ),
    }
    assert receipt["operator_sandbox_patch_command_summary"] == {
        "summary_id": "operator_sandbox_patch_command.foundation",
        "command_status": "preview_only",
        "receipt_id": "sandbox_patch_receipt",
        "command": (
            "python scripts/collect_developer_workflow_sandbox_receipt_evidence.py "
            "--receipt-id sandbox_patch_receipt "
            "--before-file .change_assurance/before.txt "
            "--after-file .change_assurance/after.txt "
            "--diff-file .change_assurance/sandbox_patch.diff "
            "--command \"apply_patch\" "
            "--rollback-command \"git apply -R .change_assurance/sandbox_patch.diff\" "
            "--evidence-ref proof://developer-workflow-v1/sandbox-patch"
        ),
        "expected_inputs": [
            ".change_assurance/before.txt",
            ".change_assurance/after.txt",
            ".change_assurance/sandbox_patch.diff",
        ],
        "expected_output": "developer_workflow_sandbox_receipt_bundle.collected.json",
        "execution_performed": False,
        "attachment_performed": False,
        "write_authority_granted": False,
        "external_effects_allowed": False,
        "operator_message": (
            "Sandbox patch command preview ready; execution and attachment remain operator-controlled"
        ),
    }
    assert receipt["operator_sandbox_patch_bundle_preview_summary"] == {
        "summary_id": "operator_sandbox_patch_bundle_preview.foundation",
        "bundle_status": "preview_only",
        "bundle_path": "developer_workflow_sandbox_receipt_bundle.collected.json",
        "included_receipt_ids": ["sandbox_patch_receipt"],
        "validation_command": (
            "python scripts/validate_developer_workflow_sandbox_receipt_bundle.py "
            "--bundle developer_workflow_sandbox_receipt_bundle.collected.json"
        ),
        "bundle_generation_performed": False,
        "validation_performed": False,
        "attachment_performed": False,
        "write_authority_granted": False,
        "external_effects_allowed": False,
        "operator_message": (
            "Sandbox patch bundle preview ready; bundle generation and validation not executed"
        ),
    }
    assert receipt["operator_sandbox_patch_readiness_compact_summary"] == {
        "summary_id": "operator_sandbox_patch_readiness_compact.foundation",
        "blocked_stage_summary_key": "operator_sandbox_patch_validation_readiness_summary",
        "blocked_stage_summary_id": "operator_sandbox_patch_validation_readiness.foundation",
        "blocked_stage_status": "blocked_missing_bundle",
        "blocked_stage_target": "developer_workflow_sandbox_receipt_bundle.collected.json",
        "next_evidence_id": "sandbox_patch_receipt_bundle_generated",
        "missing_prerequisite_count": 2,
        "required_before_unlock": [
            "sandbox_patch_receipt_bundle_generated",
            "sandbox_patch_receipt_attached",
        ],
        "external_effects_allowed": False,
        "operator_message": (
            "Sandbox patch validation blocked until the collected bundle exists and receipt is attached"
        ),
        "source_ref": "docs/21_workflow_runtime.md sandbox_patch_receipt validation readiness",
    }
    assert receipt["operator_sandbox_patch_validation_readiness_summary"] == {
        "summary_id": "operator_sandbox_patch_validation_readiness.foundation",
        "validation_status": "blocked_missing_bundle",
        "bundle_path": "developer_workflow_sandbox_receipt_bundle.collected.json",
        "validator_command": (
            "python scripts/validate_developer_workflow_sandbox_receipt_bundle.py "
            "--bundle developer_workflow_sandbox_receipt_bundle.collected.json"
        ),
        "required_before_validation": [
            "sandbox_patch_receipt_bundle_generated",
            "sandbox_patch_receipt_attached",
        ],
        "missing_prerequisite_count": 2,
        "validation_performed": False,
        "terminal_review_allowed": False,
        "external_effects_allowed": False,
        "operator_message": (
            "Sandbox patch validation blocked until the collected bundle exists and receipt is attached"
        ),
    }
    assert receipt["operator_sandbox_patch_terminal_review_summary"] == {
        "summary_id": "operator_sandbox_patch_terminal_review.foundation",
        "review_status": "blocked_until_validation",
        "review_target": "sandbox_patch_receipt",
        "required_before_review": [
            "sandbox_patch_receipt_bundle_generated",
            "sandbox_patch_receipt_attached",
            "sandbox_patch_bundle_validated",
        ],
        "missing_prerequisite_count": 3,
        "review_command": (
            "python scripts/validate_developer_workflow_sandbox_receipt_bundle.py "
            "--bundle developer_workflow_sandbox_receipt_bundle.collected.json"
        ),
        "review_performed": False,
        "approval_request_allowed": False,
        "pr_creation_allowed": False,
        "external_effects_allowed": False,
        "operator_message": (
            "Sandbox patch terminal review blocked until bundle generation, attachment, and validation complete"
        ),
    }
    assert receipt["operator_sandbox_patch_approval_readiness_summary"] == {
        "summary_id": "operator_sandbox_patch_approval_readiness.foundation",
        "approval_status": "blocked_until_terminal_review",
        "approval_target": "sandbox_patch_receipt",
        "required_before_approval": [
            "sandbox_patch_receipt_bundle_generated",
            "sandbox_patch_receipt_attached",
            "sandbox_patch_bundle_validated",
            "sandbox_patch_terminal_review_complete",
        ],
        "missing_prerequisite_count": 4,
        "approval_request_allowed": False,
        "approval_request_performed": False,
        "pr_preparation_allowed": False,
        "pr_creation_allowed": False,
        "external_effects_allowed": False,
        "operator_message": (
            "Sandbox patch approval blocked until terminal review closes with validated evidence"
        ),
    }
    assert receipt["operator_sandbox_patch_pr_preparation_readiness_summary"] == {
        "summary_id": "operator_sandbox_patch_pr_preparation_readiness.foundation",
        "preparation_status": "blocked_until_approval",
        "preparation_target": "local_pr_candidate_packet",
        "required_before_preparation": [
            "sandbox_patch_receipt_bundle_generated",
            "sandbox_patch_receipt_attached",
            "sandbox_patch_bundle_validated",
            "sandbox_patch_terminal_review_complete",
            "operator_approval_recorded",
        ],
        "missing_prerequisite_count": 5,
        "preparation_performed": False,
        "pr_preparation_allowed": False,
        "branch_push_allowed": False,
        "pr_creation_allowed": False,
        "external_effects_allowed": False,
        "operator_message": (
            "PR preparation blocked until sandbox patch approval is recorded with validated evidence"
        ),
    }
    assert receipt["operator_sandbox_patch_pr_creation_readiness_summary"] == {
        "summary_id": "operator_sandbox_patch_pr_creation_readiness.foundation",
        "creation_status": "blocked_until_pr_preparation",
        "creation_target": "github_pull_request",
        "required_before_creation": [
            "local_pr_candidate_packet_prepared",
            "local_pr_candidate_packet_validated",
            "external_pr_execution_approval_recorded",
            "branch_push_authority_bound",
            "github_pr_admission_passed",
        ],
        "missing_prerequisite_count": 5,
        "creation_performed": False,
        "branch_push_allowed": False,
        "pr_creation_allowed": False,
        "connector_call_allowed": False,
        "external_effects_allowed": False,
        "operator_message": (
            "PR creation blocked until local PR preparation and external PR approval evidence are complete"
        ),
    }
    assert receipt["operator_sandbox_patch_pr_ci_readiness_summary"] == {
        "summary_id": "operator_sandbox_patch_pr_ci_readiness.foundation",
        "ci_status": "blocked_until_pr_creation",
        "ci_target": "github_pr_ci_checks",
        "required_before_ci": [
            "github_pull_request_created",
            "pr_metadata_packet_recorded",
            "ci_gate_before_ready_for_review_witness_bound",
            "github_check_read_authority_bound",
            "pr_effect_reconciliation_pending",
        ],
        "missing_prerequisite_count": 5,
        "ci_observation_performed": False,
        "github_poll_allowed": False,
        "check_update_allowed": False,
        "ready_for_review_allowed": False,
        "external_effects_allowed": False,
        "operator_message": (
            "PR CI readiness blocked until PR creation evidence and CI observation authority are complete"
        ),
    }
    assert receipt["operator_sandbox_patch_merge_readiness_summary"] == {
        "summary_id": "operator_sandbox_patch_merge_readiness.foundation",
        "merge_status": "blocked_until_ci_pass",
        "merge_target": "protected_branch_merge",
        "required_before_merge": [
            "github_pull_request_created",
            "ci_checks_passed",
            "review_approval_recorded",
            "rollback_plan_verified",
            "merge_approval_recorded",
        ],
        "missing_prerequisite_count": 5,
        "merge_performed": False,
        "merge_allowed": False,
        "branch_write_allowed": False,
        "github_call_allowed": False,
        "external_effects_allowed": False,
        "operator_message": (
            "Merge readiness blocked until CI pass, review approval, rollback, and merge approval evidence are complete"
        ),
    }
    assert receipt["operator_sandbox_patch_release_handoff_readiness_summary"] == {
        "summary_id": "operator_sandbox_patch_release_handoff_readiness.foundation",
        "handoff_status": "blocked_until_terminal_closure",
        "handoff_target": "release_handoff_packet",
        "required_before_handoff": [
            "merge_execution_receipt_recorded",
            "terminal_closure_certificate_minted",
            "effect_reconciliation_witness_bound",
            "rollback_retention_verified",
            "release_notes_prepared",
        ],
        "missing_prerequisite_count": 5,
        "handoff_performed": False,
        "release_publication_allowed": False,
        "deployment_allowed": False,
        "public_claim_allowed": False,
        "external_effects_allowed": False,
        "operator_message": (
            "Release handoff blocked until terminal closure, reconciliation, rollback, and release-note evidence are complete"
        ),
    }
    assert receipt["operator_sandbox_patch_deployment_publication_readiness_summary"] == {
        "summary_id": "operator_sandbox_patch_deployment_publication_readiness.foundation",
        "publication_status": "blocked_until_release_handoff",
        "publication_target": "deployment_publication_closure_plan",
        "required_before_publication": [
            "release_handoff_packet_prepared",
            "deployment_publication_closure_plan_verified",
            "production_evidence_witness_bound",
            "dns_target_binding_verified",
            "operator_deployment_approval_recorded",
        ],
        "missing_prerequisite_count": 5,
        "publication_performed": False,
        "deployment_allowed": False,
        "dns_change_allowed": False,
        "production_claim_allowed": False,
        "public_endpoint_allowed": False,
        "external_effects_allowed": False,
        "operator_message": (
            "Deployment publication blocked until release handoff, production evidence, DNS binding, and deployment approval evidence are complete"
        ),
    }
    assert receipt["operator_sandbox_patch_production_monitoring_readiness_summary"] == {
        "summary_id": "operator_sandbox_patch_production_monitoring_readiness.foundation",
        "monitoring_status": "blocked_until_publication",
        "monitoring_target": "production_monitoring_witness",
        "required_before_monitoring": [
            "deployment_publication_witness_recorded",
            "public_health_witness_bound",
            "runtime_conformance_certificate_available",
            "telemetry_monitoring_plan_verified",
            "incident_rollback_recovery_plan_verified",
        ],
        "missing_prerequisite_count": 5,
        "monitoring_activation_performed": False,
        "monitor_activation_allowed": False,
        "alert_routing_allowed": False,
        "production_claim_allowed": False,
        "external_effects_allowed": False,
        "operator_message": (
            "Production monitoring blocked until deployment publication, health, runtime conformance, telemetry, and incident recovery evidence are complete"
        ),
    }
    assert receipt["operator_sandbox_patch_incident_response_readiness_summary"] == {
        "summary_id": "operator_sandbox_patch_incident_response_readiness.foundation",
        "incident_status": "blocked_until_monitoring",
        "incident_target": "incident_response_runbook",
        "required_before_incident_response": [
            "production_monitoring_witness_recorded",
            "incident_response_runbook_verified",
            "rollback_execution_receipt_template_bound",
            "containment_evidence_contract_bound",
            "operator_incident_authority_recorded",
        ],
        "missing_prerequisite_count": 5,
        "incident_response_performed": False,
        "containment_allowed": False,
        "rollback_execution_allowed": False,
        "paging_allowed": False,
        "external_effects_allowed": False,
        "operator_message": (
            "Incident response blocked until monitoring, runbook, rollback, containment, and operator authority evidence are complete"
        ),
    }
    assert receipt["operator_sandbox_patch_recovery_closure_readiness_summary"] == {
        "summary_id": "operator_sandbox_patch_recovery_closure_readiness.foundation",
        "recovery_status": "blocked_until_incident_response",
        "recovery_target": "recovery_closure_packet",
        "required_before_recovery_closure": [
            "incident_containment_evidence_recorded",
            "rollback_or_replay_receipt_recorded",
            "post_incident_verification_passed",
            "operator_recovery_closure_approval_recorded",
            "terminal_recovery_closure_packet_prepared",
        ],
        "missing_prerequisite_count": 5,
        "recovery_closure_performed": False,
        "closure_certification_allowed": False,
        "replay_promotion_allowed": False,
        "post_incident_publication_allowed": False,
        "external_effects_allowed": False,
        "operator_message": (
            "Recovery closure blocked until containment, rollback or replay, verification, approval, and terminal recovery packet evidence are complete"
        ),
    }
    assert receipt["operator_sandbox_patch_trust_ledger_readiness_summary"] == {
        "summary_id": "operator_sandbox_patch_trust_ledger_readiness.foundation",
        "ledger_status": "blocked_until_recovery_closure",
        "ledger_target": "trust_ledger_anchor_packet",
        "required_before_trust_ledger_anchor": [
            "terminal_recovery_closure_packet_prepared",
            "trust_ledger_bundle_export_prepared",
            "evidence_artifact_hashes_recorded",
            "operator_trust_ledger_anchor_approval_recorded",
            "remote_submission_preflight_passed",
        ],
        "missing_prerequisite_count": 5,
        "ledger_anchor_performed": False,
        "remote_submission_allowed": False,
        "verification_publication_allowed": False,
        "external_effects_allowed": False,
        "operator_message": (
            "Trust ledger anchoring blocked until recovery closure, export, hash, approval, and remote submission preflight evidence are complete"
        ),
    }
    assert receipt["operator_sandbox_patch_terminal_audit_export_readiness_summary"] == {
        "summary_id": "operator_sandbox_patch_terminal_audit_export_readiness.foundation",
        "audit_export_status": "blocked_until_trust_ledger_anchor",
        "audit_export_target": "terminal_audit_export_package",
        "required_before_terminal_audit_export": [
            "trust_ledger_anchor_receipt_recorded",
            "trust_ledger_anchor_verification_passed",
            "audit_bundle_integrity_report_recorded",
            "operator_audit_export_approval_recorded",
            "export_retention_boundary_verified",
        ],
        "missing_prerequisite_count": 5,
        "audit_export_performed": False,
        "archive_submission_allowed": False,
        "external_publication_allowed": False,
        "external_effects_allowed": False,
        "operator_message": (
            "Terminal audit export blocked until trust ledger anchor, verification, integrity, approval, and retention evidence are complete"
        ),
    }
    assert receipt["operator_sandbox_patch_foundation_closure_readiness_summary"] == {
        "summary_id": "operator_sandbox_patch_foundation_closure_readiness.foundation",
        "foundation_closure_status": "blocked_until_terminal_audit_export",
        "foundation_closure_target": "foundation_closure_certificate",
        "required_before_foundation_closure": [
            "terminal_audit_export_package_prepared",
            "operator_final_closure_approval_recorded",
            "all_no_effect_denials_preserved",
            "open_gap_register_reviewed",
            "next_iteration_handoff_recorded",
        ],
        "missing_prerequisite_count": 5,
        "foundation_closure_certified": False,
        "promotion_allowed": False,
        "handoff_publication_allowed": False,
        "external_effects_allowed": False,
        "operator_message": (
            "Foundation closure blocked until terminal audit export, final approval, denial preservation, gap review, and next-iteration handoff evidence are complete"
        ),
    }
    assert receipt["operator_sandbox_patch_iteration_resume_readiness_summary"] == {
        "summary_id": "operator_sandbox_patch_iteration_resume_readiness.foundation",
        "iteration_resume_status": "blocked_until_foundation_closure",
        "iteration_resume_target": "next_iteration_intake_packet",
        "required_before_iteration_resume": [
            "foundation_closure_certificate_recorded",
            "next_iteration_scope_declared",
            "next_iteration_risk_boundary_reviewed",
            "next_iteration_evidence_queue_seeded",
            "operator_resume_intent_recorded",
        ],
        "missing_prerequisite_count": 5,
        "next_iteration_started": False,
        "automatic_resume_allowed": False,
        "authority_carryover_allowed": False,
        "external_effects_allowed": False,
        "operator_message": (
            "Iteration resume blocked until foundation closure, next scope, risk boundary, evidence queue, and operator resume intent evidence are complete"
        ),
    }
    assert receipt["operator_sandbox_patch_next_scope_admission_readiness_summary"] == {
        "summary_id": "operator_sandbox_patch_next_scope_admission_readiness.foundation",
        "next_scope_admission_status": "blocked_until_iteration_resume",
        "next_scope_target": "next_scope_admission_packet",
        "required_before_next_scope_admission": [
            "next_iteration_intake_packet_prepared",
            "next_scope_boundaries_declared",
            "next_scope_acceptance_criteria_recorded",
            "next_scope_risk_review_recorded",
            "next_scope_rollback_expectations_recorded",
        ],
        "missing_prerequisite_count": 5,
        "scope_admitted": False,
        "execution_allowed": False,
        "authority_promotion_allowed": False,
        "external_effects_allowed": False,
        "operator_message": (
            "Next scope admission blocked until intake, boundaries, acceptance criteria, risk review, and rollback expectation evidence are complete"
        ),
    }
    assert receipt["operator_handoff_summary"] == {
        "summary_id": "operator_handoff.foundation",
        "handoff_status": "ready_for_local_resume",
        "task": "Mullu Developer Workflow v1",
        "current_milestone": "collect_sandbox_receipts",
        "current_blocker": "sandbox_receipts_incomplete",
        "next_action": "complete sandbox patch, test, diff, and terminal receipts",
        "next_evidence_id": "sandbox_patch_receipt",
        "pending_evidence_count": 7,
        "approval_boundary": "before_pr_or_real_world_effect",
        "recommended_mode": "fast",
        "local_resume_allowed": True,
        "forbidden_effects": [
            "external_pr_creation",
            "branch_push",
            "merge",
            "deployment",
            "connector_write",
            "real_world_effect",
        ],
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "operator_message": (
            "Handoff ready for local resume; milestone collect_sandbox_receipts; "
            "next evidence sandbox_patch_receipt"
        ),
    }
    assert receipt["operator_review_readiness_summary"] == {
        "summary_id": "operator_review_readiness.foundation",
        "review_status": "awaiting_evidence",
        "review_ready": False,
        "review_blocker": "sandbox_receipts_incomplete",
        "required_evidence_count": 7,
        "completed_evidence_count": 0,
        "pending_evidence_count": 7,
        "next_evidence_id": "sandbox_patch_receipt",
        "next_review_action": "complete local evidence receipts before review",
        "approval_boundary": "before_pr_or_real_world_effect",
        "pr_creation_allowed": False,
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "operator_message": "Review readiness awaiting evidence; 0/7 evidence receipts complete",
    }
    assert receipt["operator_review_packet_summary"] == {
        "summary_id": "operator_review_packet.foundation",
        "packet_status": "awaiting_evidence",
        "review_ready": False,
        "review_blocker": "sandbox_receipts_incomplete",
        "completed_evidence_count": 0,
        "required_evidence_count": 7,
        "pending_evidence_count": 7,
        "next_evidence_id": "sandbox_patch_receipt",
        "next_packet_action": "complete local evidence receipts before review packet",
        "approval_boundary": "before_pr_or_real_world_effect",
        "approval_required_now": False,
        "pr_creation_allowed": False,
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "operator_message": "Review packet awaiting evidence; 7 evidence receipts pending",
    }
    assert receipt["operator_blocker_summary"] == {
        "summary_id": "operator_blocker.foundation",
        "blocker_status": "blocked",
        "active_blocker": "sandbox_receipts_incomplete",
        "blocker_class": "local_evidence",
        "clearing_action": "attach before state, after state, diff, command, and rollback receipt",
        "next_evidence_id": "sandbox_patch_receipt",
        "pending_evidence_count": 7,
        "approval_required_now": False,
        "approval_boundary": "before_pr_or_real_world_effect",
        "local_resume_allowed": True,
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "operator_message": (
            "Blocker sandbox_receipts_incomplete is local evidence; "
            "next evidence sandbox_patch_receipt"
        ),
    }
    assert receipt["operator_packet_summary"] == {
        "summary_id": "operator_packet.foundation",
        "packet_status": "awaiting_packets",
        "sandbox_receipt_status": "not_attached",
        "attachment_status": "awaiting_attachments",
        "local_proof_status": "not_attached",
        "rollback_receipt_status": "not_attached",
        "pr_readiness_status": "awaiting_sandbox_receipts",
        "completed_packet_count": 0,
        "required_packet_count": 5,
        "next_packet": "sandbox_patch_receipt",
        "next_packet_action": "attach before state, after state, diff, command, and rollback receipt",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "operator_message": "Packet summary awaiting sandbox_patch_receipt; 7 evidence receipts pending",
    }
    assert receipt["operator_authority_summary"] == {
        "summary_id": "operator_authority.foundation",
        "authority_status": "local_lab_only",
        "local_prepare_allowed": True,
        "review_allowed": False,
        "approval_required_now": False,
        "approval_boundary": "before_pr_or_real_world_effect",
        "pr_creation_allowed": False,
        "branch_push_allowed": False,
        "connector_write_allowed": False,
        "real_world_effects_allowed": False,
        "forbidden_effect_count": 4,
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "operator_message": (
            "Authority local_lab_only; local preparation allowed; "
            "PR creation, branch push, connector writes, and real-world effects denied"
        ),
    }
    assert receipt["operator_risk_summary"] == {
        "summary_id": "operator_risk.foundation",
        "risk_status": "low_local_lab",
        "risk_level": "low",
        "risk_driver": "sandbox_receipts_incomplete",
        "risk_scope": "local_lab_only",
        "safe_candidate_count": 7,
        "dangerous_blocker_count": 7,
        "pending_evidence_count": 7,
        "approval_boundary": "before_pr_or_real_world_effect",
        "rollback_ready": False,
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "operator_message": "Risk is low because execution is local-lab only; 7 dangerous zones remain blocked",
    }
    assert receipt["operator_approval_packet_summary"] == {
        "summary_id": "operator_approval_packet.foundation",
        "packet_status": "awaiting_evidence",
        "approval_required": True,
        "approval_status": "pending",
        "approval_missing": True,
        "current_blocker": "sandbox_receipts_incomplete",
        "completed_evidence_count": 0,
        "required_evidence_count": 7,
        "pending_evidence_count": 7,
        "next_evidence_id": "sandbox_patch_receipt",
        "next_approval_action": "complete sandbox receipts before requesting approval",
        "approval_target_href": "/operator/control-tower/status-receipt?focus_id=sandbox_patch_receipt",
        "ready_for_pr_candidate_preparation": False,
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "operator_message": "Approval packet awaiting evidence; 7 evidence receipts pending",
    }
    assert receipt["operator_evidence_gap_summary"] == {
        "summary_id": "operator_evidence_gap.foundation",
        "gap_status": "evidence_incomplete",
        "gap_class": "local_receipts",
        "completed_evidence_count": 0,
        "required_evidence_count": 7,
        "pending_evidence_count": 7,
        "next_evidence_id": "sandbox_patch_receipt",
        "next_gap_action": "attach before state, after state, diff, command, and rollback receipt",
        "approval_blocked": True,
        "local_continuation_allowed": True,
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "operator_message": "Evidence gap: 7 of 7 receipts still pending",
    }
    assert receipt["operator_rollback_gap_summary"] == {
        "summary_id": "operator_rollback_gap.foundation",
        "gap_status": "rollback_receipts_incomplete",
        "readiness_verdict": "awaiting_selection",
        "command_status": "awaiting_selection",
        "selected_artifact_count": 0,
        "receipt_available_count": 0,
        "receipt_required_count": 3,
        "next_rollback_action": "select at least one generated artifact before running rollback flow",
        "dry_run_required": True,
        "execution_requires_execute_flag": True,
        "rollback_ready": False,
        "approval_status": "pending",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "operator_message": "Rollback gap: 0/3 rollback receipts available",
    }
    assert receipt["operator_pr_gap_summary"] == {
        "summary_id": "operator_pr_gap.foundation",
        "gap_status": "awaiting_sandbox_receipts",
        "first_blocker": "sandbox_receipts",
        "ready_for_external_pr_execution": False,
        "next_evidence_count": 7,
        "receipt_completed_count": 0,
        "receipt_required_count": 4,
        "preview_only": True,
        "pr_creation_allowed": False,
        "branch_push_allowed": False,
        "execution_performed": False,
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "operator_message": "PR gap: awaiting_sandbox_receipts; first blocker sandbox_receipts",
    }
    assert receipt["operator_dashboard_summary"] == {
        "summary_id": "operator_dashboard.foundation",
        "task": "Mullu Developer Workflow v1",
        "status": "preflight_ready",
        "current_milestone": "collect_sandbox_receipts",
        "blocker": "sandbox_receipts_incomplete",
        "next_action": "complete sandbox patch, test, diff, and terminal receipts",
        "recommended_mode": "fast",
        "receipt_completed_count": 0,
        "receipt_required_count": 4,
        "pending_unlock_count": receipt["control_system_summary"]["pending_unlock_count"],
        "safe_candidate_count": 7,
        "dangerous_blocker_count": 7,
        "next_unlock": "approval",
        "action_needed": "review diff receipt before approving pull request candidate",
        "risk": "low, local lab only",
        "operator_message": (
            "Dashboard summary: collect_sandbox_receipts; next action "
            "complete sandbox patch, test, diff, and terminal receipts"
        ),
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }
    assert receipt["workflow_run"]["current_task_id"] == "sandbox_change"
    assert (
        receipt["source_refs"]["operator_action_card"]
        == "workflow_monitor.metadata.operator_action_card"
    )
    assert (
        receipt["source_refs"]["control_tower_headline_summary"]
        == "capability_health.metadata.control_system_summary + workflow_monitor.metadata.friction_reduction_summary"
    )
    assert (
        receipt["source_refs"]["local_lab_readiness_summary"]
        == "workflow_monitor.metadata.evidence_progress_summary + workflow_monitor.metadata.local_rollback_flow_readiness_summary"
    )
    assert (
        receipt["source_refs"]["local_resume_plan_summary"]
        == "workflow_monitor.metadata.operator_decision_summary + workflow_monitor.metadata.evidence_progress_summary"
    )
    assert (
        receipt["source_refs"]["next_action_summary"]
        == "workflow_monitor.metadata.next_action_summary"
    )
    assert (
        receipt["source_refs"]["approval_readiness_summary"]
        == "workflow_monitor.metadata.approval_readiness_summary"
    )
    assert (
        receipt["source_refs"]["operator_decision_summary"]
        == "workflow_monitor.metadata.operator_decision_summary"
    )
    assert (
        receipt["source_refs"]["friction_reduction_summary"]
        == "workflow_monitor.metadata.friction_reduction_summary"
    )
    assert (
        receipt["source_refs"]["safe_local_action_queue_summary"]
        == "capability_health.metadata.safe_local_action_queue_summary"
    )
    assert (
        receipt["source_refs"]["safe_automatic_action_candidates"]
        == "capability_health.metadata.safe_automatic_action_candidates"
    )
    assert (
        receipt["source_refs"]["dangerous_action_blocker_summary"]
        == "capability_health.metadata.dangerous_action_blocker_summary"
    )
    assert (
        receipt["source_refs"]["dangerous_zone_blockers"]
        == "capability_health.metadata.dangerous_zone_blockers"
    )
    assert (
        receipt["source_refs"]["lab_real_world_summary"]
        == "capability_health.metadata.lab_real_world_summary"
    )
    assert (
        receipt["source_refs"]["approval_boundary_summary"]
        == "capability_health.metadata.approval_boundary_summary"
    )
    assert (
        receipt["source_refs"]["rollback_control_summary"]
        == "capability_health.metadata.rollback_control_summary"
    )
    assert (
        receipt["source_refs"]["capability_registry_summary"]
        == "capability_health.metadata.capability_registry_summary"
    )
    assert (
        receipt["source_refs"]["friction_mode_summary"]
        == "capability_health.metadata.friction_mode_summary"
    )
    assert (
        receipt["source_refs"]["safe_vs_dangerous_summary"]
        == "capability_health.metadata.safe_vs_dangerous_summary"
    )
    assert (
        receipt["source_refs"]["unlock_readiness_summary"]
        == "capability_health.metadata.unlock_readiness_summary"
    )
    assert (
        receipt["source_refs"]["control_system_summary"]
        == "capability_health.metadata.control_system_summary"
    )
    assert (
        receipt["source_refs"]["workflow_monitor_summary"]
        == "workflow_monitor.metadata.workflow_monitor_summary"
    )
    assert receipt["source_refs"]["focus"] == "workflow_monitor.metadata.sandbox_to_pr_focus"
    assert receipt["source_refs"]["sandbox_to_pr_summary"] == "workflow_monitor.metadata.sandbox_to_pr_summary"
    assert (
        receipt["source_refs"]["sandbox_receipt_bundle_summary"]
        == "workflow_monitor.metadata.sandbox_receipt_bundle_summary"
    )
    assert (
        receipt["source_refs"]["sandbox_receipt_attachments"]
        == "workflow_monitor.metadata.sandbox_receipt_attachment_packet"
    )
    assert (
        receipt["source_refs"]["sandbox_receipt_attachment_readiness_summary"]
        == "workflow_monitor.metadata.sandbox_receipt_attachment_readiness_summary"
    )
    assert (
        receipt["source_refs"]["local_sandbox_proof_report"]
        == "workflow_monitor.metadata.local_sandbox_proof_report"
    )
    assert (
        receipt["source_refs"]["local_sandbox_proof_readiness_summary"]
        == "workflow_monitor.metadata.local_sandbox_proof_readiness_summary"
    )
    assert (
        receipt["source_refs"]["local_rollback_summary_packet"]
        == "workflow_monitor.metadata.local_rollback_summary_packet"
    )
    assert (
        receipt["source_refs"]["local_rollback_approval_packet"]
        == "workflow_monitor.metadata.local_rollback_approval_packet"
    )
    assert (
        receipt["source_refs"]["local_rollback_execution_receipt"]
        == "workflow_monitor.metadata.local_rollback_execution_receipt"
    )
    assert (
        receipt["source_refs"]["local_rollback_receipts_summary"]
        == "workflow_monitor.metadata.local_rollback_receipts_summary"
    )
    assert (
        receipt["source_refs"]["local_rollback_flow_command"]
        == "workflow_monitor.metadata.local_rollback_flow_command"
    )
    assert (
        receipt["source_refs"]["local_rollback_flow_readiness_summary"]
        == "workflow_monitor.metadata.local_rollback_flow_readiness_summary"
    )
    assert receipt["source_refs"]["pr_readiness"] == "workflow_monitor.metadata.pr_readiness_bundle"
    assert receipt["source_refs"]["pr_readiness_summary"] == "workflow_monitor.metadata.pr_readiness_summary"
    assert (
        receipt["source_refs"]["evidence_progress_summary"]
        == "workflow_monitor.metadata.evidence_progress_summary"
    )
    assert (
        receipt["source_refs"]["developer_workflow_operator_receipt_summary"]
        == "workflow_monitor.metadata.developer_workflow_operator_receipt_summary"
    )
    assert (
        receipt["source_refs"]["developer_workflow_readiness_summary"]
        == "workflow_monitor.metadata.developer_workflow_readiness_summary"
    )
    assert (
        receipt["source_refs"]["developer_workflow_milestone_summary"]
        == "workflow_monitor.metadata.developer_workflow_milestone_summary"
    )
    assert (
        receipt["source_refs"]["developer_workflow_completion_summary"]
        == (
            "workflow_monitor.metadata.developer_workflow_milestone_summary + "
            "workflow_monitor.metadata.evidence_progress_summary"
        )
    )
    assert (
        receipt["source_refs"]["operator_terminal_closure_summary"]
        == (
            "workflow_monitor.metadata.developer_workflow_milestone_summary + "
            "workflow_monitor.metadata.evidence_progress_summary"
        )
    )
    assert (
        receipt["source_refs"]["operator_resume_checkpoint_summary"]
        == (
            "workflow_monitor.metadata.friction_reduction_summary + "
            "workflow_monitor.metadata.operator_decision_summary"
        )
    )
    assert (
        receipt["source_refs"]["operator_sandbox_milestone_summary"]
        == (
            "workflow_monitor.metadata.developer_workflow_milestone_summary + "
            "workflow_monitor.metadata.evidence_progress_summary"
        )
    )
    assert (
        receipt["source_refs"]["operator_sandbox_receipt_checklist_summary"]
        == (
            "workflow_monitor.metadata.evidence_progress_summary + "
            "workflow_monitor.metadata.sandbox_receipt_attachment_readiness_summary"
        )
    )
    assert (
        receipt["source_refs"]["operator_sandbox_patch_receipt_summary"]
        == (
            "workflow_monitor.metadata.sandbox_receipt_attachment_readiness_summary + "
            "workflow_monitor.metadata.evidence_progress_summary"
        )
    )
    assert (
        receipt["source_refs"]["operator_sandbox_patch_command_summary"]
        == "docs/21_workflow_runtime.md sandbox_patch_receipt collection command"
    )
    assert (
        receipt["source_refs"]["operator_sandbox_patch_bundle_preview_summary"]
        == "docs/21_workflow_runtime.md sandbox_patch_receipt bundle validation"
    )
    assert (
        receipt["source_refs"]["operator_sandbox_patch_readiness_compact_summary"]
        == (
            "gateway.operator_sandbox_patch_readiness.SANDBOX_PATCH_READINESS_REGISTRY "
            "compact first-blocker projection"
        )
    )
    assert (
        receipt["source_refs"]["operator_sandbox_patch_validation_readiness_summary"]
        == "docs/21_workflow_runtime.md sandbox_patch_receipt validation readiness"
    )
    assert (
        receipt["source_refs"]["operator_sandbox_patch_terminal_review_summary"]
        == "docs/21_workflow_runtime.md sandbox_patch_receipt terminal review readiness"
    )
    assert (
        receipt["source_refs"]["operator_sandbox_patch_approval_readiness_summary"]
        == "docs/21_workflow_runtime.md sandbox_patch_receipt approval readiness"
    )
    assert (
        receipt["source_refs"]["operator_sandbox_patch_pr_preparation_readiness_summary"]
        == "docs/21_workflow_runtime.md sandbox_patch_receipt PR preparation readiness"
    )
    assert (
        receipt["source_refs"]["operator_sandbox_patch_pr_creation_readiness_summary"]
        == "docs/21_workflow_runtime.md sandbox_patch_receipt PR creation readiness"
    )
    assert (
        receipt["source_refs"]["operator_sandbox_patch_pr_ci_readiness_summary"]
        == "docs/21_workflow_runtime.md sandbox_patch_receipt PR CI readiness"
    )
    assert (
        receipt["source_refs"]["operator_sandbox_patch_merge_readiness_summary"]
        == "docs/21_workflow_runtime.md sandbox_patch_receipt merge readiness"
    )
    assert (
        receipt["source_refs"]["operator_sandbox_patch_release_handoff_readiness_summary"]
        == "docs/21_workflow_runtime.md sandbox_patch_receipt release handoff readiness"
    )
    assert (
        receipt["source_refs"]["operator_sandbox_patch_deployment_publication_readiness_summary"]
        == "docs/21_workflow_runtime.md sandbox_patch_receipt deployment publication readiness"
    )
    assert (
        receipt["source_refs"]["operator_sandbox_patch_production_monitoring_readiness_summary"]
        == "docs/21_workflow_runtime.md sandbox_patch_receipt production monitoring readiness"
    )
    assert (
        receipt["source_refs"]["operator_sandbox_patch_incident_response_readiness_summary"]
        == "docs/21_workflow_runtime.md sandbox_patch_receipt incident response readiness"
    )
    assert (
        receipt["source_refs"]["operator_sandbox_patch_recovery_closure_readiness_summary"]
        == "docs/21_workflow_runtime.md sandbox_patch_receipt recovery closure readiness"
    )
    assert (
        receipt["source_refs"]["operator_sandbox_patch_trust_ledger_readiness_summary"]
        == "docs/21_workflow_runtime.md sandbox_patch_receipt trust ledger readiness"
    )
    assert (
        receipt["source_refs"]["operator_sandbox_patch_terminal_audit_export_readiness_summary"]
        == "docs/21_workflow_runtime.md sandbox_patch_receipt terminal audit export readiness"
    )
    assert (
        receipt["source_refs"]["operator_sandbox_patch_foundation_closure_readiness_summary"]
        == "docs/21_workflow_runtime.md sandbox_patch_receipt foundation closure readiness"
    )
    assert (
        receipt["source_refs"]["operator_sandbox_patch_iteration_resume_readiness_summary"]
        == "docs/21_workflow_runtime.md sandbox_patch_receipt iteration resume readiness"
    )
    assert (
        receipt["source_refs"]["operator_sandbox_patch_next_scope_admission_readiness_summary"]
        == "docs/21_workflow_runtime.md sandbox_patch_receipt next scope admission readiness"
    )
    assert (
        receipt["source_refs"]["operator_handoff_summary"]
        == (
            "workflow_monitor.metadata.developer_workflow_milestone_summary + "
            "workflow_monitor.metadata.operator_decision_summary"
        )
    )
    assert (
        receipt["source_refs"]["operator_review_readiness_summary"]
        == (
            "workflow_monitor.metadata.evidence_progress_summary + "
            "workflow_monitor.metadata.approval_readiness_summary"
        )
    )
    assert (
        receipt["source_refs"]["operator_review_packet_summary"]
        == (
            "workflow_monitor.metadata.approval_readiness_summary + "
            "workflow_monitor.metadata.evidence_progress_summary"
        )
    )
    assert (
        receipt["source_refs"]["operator_blocker_summary"]
        == (
            "workflow_monitor.metadata.developer_workflow_milestone_summary + "
            "workflow_monitor.metadata.evidence_progress_summary"
        )
    )
    assert (
        receipt["source_refs"]["operator_packet_summary"]
        == (
            "workflow_monitor.metadata.sandbox_receipt_bundle_summary + "
            "workflow_monitor.metadata.local_rollback_receipts_summary"
        )
    )
    assert (
        receipt["source_refs"]["operator_authority_summary"]
        == (
            "workflow_monitor.metadata.approval_readiness_summary + "
            "capability_health.metadata.lab_real_world_summary"
        )
    )
    assert (
        receipt["source_refs"]["operator_risk_summary"]
        == (
            "capability_health.metadata.dangerous_action_blocker_summary + "
            "workflow_monitor.metadata.evidence_progress_summary"
        )
    )
    assert (
        receipt["source_refs"]["operator_approval_packet_summary"]
        == (
            "workflow_monitor.metadata.approval_readiness_summary + "
            "workflow_monitor.metadata.evidence_progress_summary"
        )
    )
    assert (
        receipt["source_refs"]["operator_evidence_gap_summary"]
        == (
            "workflow_monitor.metadata.evidence_progress_summary + "
            "workflow_monitor.metadata.friction_reduction_summary"
        )
    )
    assert (
        receipt["source_refs"]["operator_rollback_gap_summary"]
        == (
            "workflow_monitor.metadata.local_rollback_flow_readiness_summary + "
            "workflow_monitor.metadata.local_rollback_receipts_summary"
        )
    )
    assert (
        receipt["source_refs"]["operator_pr_gap_summary"]
        == (
            "workflow_monitor.metadata.pr_readiness_summary + "
            "workflow_monitor.metadata.pr_readiness_bundle"
        )
    )
    assert (
        receipt["source_refs"]["operator_dashboard_summary"]
        == (
            "capability_health.metadata.control_system_summary + "
            "workflow_monitor.metadata.developer_workflow_milestone_summary"
        )
    )


def test_operator_control_tower_sandbox_patch_readiness_read_model_route() -> None:
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    response = client.get("/operator/control-tower/sandbox-patch-readiness/read-model")

    assert response.status_code == 200
    read_model = response.json()
    schema = json.loads(SANDBOX_PATCH_READINESS_COMPACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(read_model)
    summary = read_model["summary"]
    assert read_model["read_model_id"] == "operator_sandbox_patch_readiness_compact.read_model"
    assert read_model["projection_only"] is True
    assert read_model["external_effects_allowed"] is False
    assert read_model["source_ref"] == (
        "gateway.operator_sandbox_patch_readiness.SANDBOX_PATCH_READINESS_REGISTRY "
        "compact first-blocker projection"
    )
    assert summary["blocked_stage_summary_key"] == "operator_sandbox_patch_validation_readiness_summary"
    assert summary["blocked_stage_status"] == "blocked_missing_bundle"
    assert summary["next_evidence_id"] == "sandbox_patch_receipt_bundle_generated"
    assert summary["missing_prerequisite_count"] == 2
    assert summary["external_effects_allowed"] is False


def test_operator_control_tower_developer_workflow_status_read_model_route(monkeypatch, tmp_path: Path) -> None:
    receipt_path = tmp_path / "developer_workflow_operator_receipt.generated.json"
    receipt_path.write_text(
        json.dumps(_developer_workflow_operator_receipt(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(server_module, "LOCAL_DEVELOPER_WORKFLOW_OPERATOR_RECEIPT_PATH", receipt_path)
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    response = client.get("/operator/control-tower/developer-workflow-status/read-model")

    assert response.status_code == 200
    read_model = response.json()
    schema = json.loads(DEVELOPER_WORKFLOW_STATUS_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(read_model)
    assert read_model["read_model_id"] == "operator_developer_workflow_status.read_model"
    assert read_model["projection_only"] is True
    assert read_model["external_effects_allowed"] is False
    assert read_model["task"] == "Governed Developer Workflow v1"
    assert read_model["status"] == "awaiting_external_pr_approval"
    assert read_model["reason"] == "operator external PR approval missing"
    assert read_model["next_unlock"] == "external_approval_witness"
    assert read_model["risk"] == "external repository write"
    assert read_model["action_needed"] == "approve or defer external PR execution"
    assert read_model["summary"]["sandbox_receipts_completed"] == 4
    assert read_model["summary"]["local_candidate_ready"] is True
    assert read_model["summary"]["pr_tool_admitted"] is True
    assert read_model["summary"]["external_approval_status"] == "pending"
    assert read_model["summary"]["action_banner"] == (
        "Action needed before PR execution: provide external_approval_witness; "
        "external approval is pending."
    )
    assert read_model["summary"]["command_preview_rendered"] is False
    assert read_model["summary"]["execution_performed"] is False
    capability_summary = read_model["capability_summary"]
    assert capability_summary["capability_id"] == "mullu_developer_workflow.v1"
    assert capability_summary["mode"] == "lab"
    assert capability_summary["current_level"] == "L4"
    assert capability_summary["next_level"] == "L5"
    assert capability_summary["status"] == "approval_required"
    assert capability_summary["blocked_reason"] == "external approval pending"
    assert capability_summary["next_evidence"] == ["external_approval_witness", "command_preview"]
    assert capability_summary["next_evidence_count"] == 2
    assert capability_summary["external_effects_allowed"] is False
    assert capability_summary["rollback_required"] is True
    assert "prepare PR candidate" in capability_summary["allowed_actions"]
    assert "create PR" in capability_summary["blocked_actions"]
    assert "push branch" in capability_summary["blocked_actions"]
    control_summary = read_model["control_summary"]
    assert control_summary["summary_id"] == "developer_workflow_control_summary.v1"
    assert control_summary["contract_id"] == "operator_dashboard_control_summary.v1"
    assert control_summary["operator_message"] == read_model["summary"]["action_banner"]
    assert control_summary["action_banner"] == read_model["summary"]["action_banner"]
    assert control_summary["capability_id"] == capability_summary["capability_id"]
    assert control_summary["mode"] == capability_summary["mode"]
    assert control_summary["current_level"] == capability_summary["current_level"]
    assert control_summary["next_level"] == capability_summary["next_level"]
    assert control_summary["status"] == capability_summary["status"]
    assert control_summary["blocked_reason"] == capability_summary["blocked_reason"]
    assert control_summary["next_unlock"] == "external_approval_witness"
    assert control_summary["next_evidence_count"] == capability_summary["next_evidence_count"]
    assert control_summary["external_effects_allowed"] is False
    assert control_summary["rollback_required"] is True


def test_operator_control_tower_read_model_surfaces_generated_operator_receipt(
    monkeypatch,
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "developer_workflow_operator_receipt.generated.json"
    receipt_path.write_text(
        json.dumps(_developer_workflow_operator_receipt(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(server_module, "LOCAL_DEVELOPER_WORKFLOW_OPERATOR_RECEIPT_PATH", receipt_path)
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    response = client.get("/operator/control-tower/read-model?include_developer_workflow_operator_receipt=true")

    assert response.status_code == 200
    panels = {item["panel"]: item for item in response.json()["panels"]}
    workflow_metadata = panels["workflow_monitor"]["metadata"]
    operator_receipt = workflow_metadata["developer_workflow_operator_receipt"]
    operator_summary = workflow_metadata["developer_workflow_operator_receipt_summary"]
    assert operator_receipt["readiness_status"] == "awaiting_external_pr_approval"
    assert operator_receipt["solver_outcome"] == "AwaitingEvidence"
    assert operator_receipt["next_evidence"] == ["external_approval_witness", "command_preview"]
    assert operator_receipt["external_approval_status"] == "pending"
    assert operator_receipt["local_candidate_ready"] is True
    assert operator_receipt["pr_tool_admitted"] is True
    assert operator_receipt["external_effects_allowed"] is False
    assert operator_receipt["rollback_required"] is True
    assert operator_receipt["rollback_command_count"] == 2
    assert operator_receipt["rollback_command_preview"] == (
        "git push origin --delete codex/developer-workflow-local-readiness"
    )
    assert operator_receipt["evidence_chain"] == [
        {
            "stage": "sandbox_receipts",
            "status": "receipts_complete",
            "ref": ".change_assurance/developer_workflow_sandbox_receipt_bundle.generated.json",
        },
        {
            "stage": "pr_preparation_approval",
            "status": "approved",
            "ref": ".change_assurance/pr_preparation_approval_packet.approved.json",
        },
        {
            "stage": "local_pr_candidate",
            "status": "ready_for_pr_tool",
            "ref": ".change_assurance/local_pr_candidate_packet.generated.json",
        },
        {
            "stage": "external_approval",
            "status": "pending",
            "ref": ".change_assurance/external_pr_execution_approval_witness.pending.json",
        },
    ]
    assert operator_receipt["execution_performed"] is False
    assert operator_receipt["command_preview_rendered"] is False
    assert operator_summary["readiness_status"] == "awaiting_external_pr_approval"
    assert operator_summary["external_approval_status"] == "pending"
    assert operator_summary["local_candidate_ready"] is True
    assert operator_summary["pr_tool_admitted"] is True
    assert operator_summary["rollback_required"] is True
    assert operator_summary["rollback_command_count"] == 2
    assert operator_summary["evidence_chain_count"] == 4
    assert operator_summary["execution_performed"] is False
    assert operator_summary["external_effects_allowed"] is False


def test_operator_control_tower_html_action_banner_uses_generated_receipt(
    monkeypatch,
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "developer_workflow_operator_receipt.generated.json"
    receipt_path.write_text(
        json.dumps(_developer_workflow_operator_receipt(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(server_module, "LOCAL_DEVELOPER_WORKFLOW_OPERATOR_RECEIPT_PATH", receipt_path)
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    response = client.get("/operator/control-tower?include_developer_workflow_operator_receipt=true")

    assert response.status_code == 200
    assert "Action needed before PR execution: provide external_approval_witness" in response.text
    assert "external approval is pending" in response.text
    assert "Control contract: operator_dashboard_control_summary.v1" in response.text
    assert "Control summary: developer_workflow_control_summary.v1" in response.text
    assert "Capability: mullu_developer_workflow.v1" in response.text
    assert "Mode: lab" in response.text
    assert "Current level: L4" in response.text
    assert "Next level: L5" in response.text
    assert "Capability status: approval_required" in response.text
    assert "Blocked reason: external approval pending" in response.text
    assert "Allowed actions: prepare diff, validate evidence, write sandbox files, run tests, prepare PR candidate" in response.text
    assert "Blocked actions: create PR, push branch, connector call, merge, deploy" in response.text
    assert "External approval: pending" in response.text
    assert "PR tool admitted: true" in response.text
    assert "Rollback required: true" in response.text
    assert "Rollback commands: 2" in response.text
    assert "Rollback preview: git push origin --delete codex/developer-workflow-local-readiness" in response.text
    assert (
        "Evidence chain: sandbox_receipts=receipts_complete -&gt; "
        "pr_preparation_approval=approved -&gt; "
        "local_pr_candidate=ready_for_pr_tool -&gt; external_approval=pending"
    ) in response.text
    assert "External effects allowed: false" in response.text


def test_developer_workflow_operator_action_banner_cases() -> None:
    pending = developer_workflow_operator_action_banner(
        external_ready=False,
        external_approval_status="pending",
        command_preview_rendered=False,
        next_unlock="external_approval_witness",
        evidence_text="external_approval_witness, command_preview",
    )
    preview_missing = developer_workflow_operator_action_banner(
        external_ready=False,
        external_approval_status="approved",
        command_preview_rendered=False,
        next_unlock="command_preview",
        evidence_text="command_preview",
    )
    approved_external = developer_workflow_operator_action_banner(
        external_ready=True,
        external_approval_status="approved",
        command_preview_rendered=True,
        next_unlock="none",
        evidence_text="none",
    )

    assert pending == (
        "Action needed before PR execution: provide external_approval_witness; "
        "external approval is pending."
    )
    assert preview_missing == "Action needed before PR execution: render command preview."
    assert approved_external == (
        "PR execution remains disabled in this dashboard; use the approved external path only."
    )


def test_developer_workflow_capability_summary_cases() -> None:
    summary = developer_workflow_capability_summary(
        {
            "ready_for_external_pr_execution": False,
            "external_approval_status": "pending",
            "local_candidate_ready": True,
            "pr_tool_admitted": True,
            "sandbox_receipts_completed": 4,
            "sandbox_receipts_required": 4,
            "next_evidence": ["external_approval_witness", "command_preview"],
            "rollback_required": True,
        }
    )

    assert summary["capability_id"] == "mullu_developer_workflow.v1"
    assert summary["mode"] == "lab"
    assert summary["current_level"] == "L4"
    assert summary["next_level"] == "L5"
    assert summary["status"] == "approval_required"
    assert summary["blocked_reason"] == "external approval pending"
    assert summary["next_evidence"] == ["external_approval_witness", "command_preview"]
    assert summary["next_evidence_count"] == 2
    assert summary["external_effects_allowed"] is False
    assert summary["rollback_required"] is True
    assert "prepare PR candidate" in summary["allowed_actions"]
    assert "create PR" in summary["blocked_actions"]
    assert "push branch" in summary["blocked_actions"]


def test_operator_dashboard_control_summary_contract_cases() -> None:
    summary = operator_dashboard_control_summary(
        summary_id="example_control_summary.v1",
        operator_message="Action needed: provide approval",
        next_unlock="approval",
        capability_summary={
            "capability_id": "example.capability",
            "mode": "lab",
            "current_level": "L2",
            "next_level": "L3",
            "status": "approval_required",
            "blocked_reason": "approval pending",
            "next_evidence_count": 1,
            "external_effects_allowed": False,
            "rollback_required": True,
        },
    )

    assert summary["contract_id"] == "operator_dashboard_control_summary.v1"
    assert summary["summary_id"] == "example_control_summary.v1"
    assert summary["operator_message"] == "Action needed: provide approval"
    assert summary["action_banner"] == "Action needed: provide approval"
    assert summary["capability_id"] == "example.capability"
    assert summary["mode"] == "lab"
    assert summary["current_level"] == "L2"
    assert summary["next_level"] == "L3"
    assert summary["status"] == "approval_required"
    assert summary["blocked_reason"] == "approval pending"
    assert summary["next_unlock"] == "approval"
    assert summary["next_evidence_count"] == 1
    assert summary["external_effects_allowed"] is False
    assert summary["rollback_required"] is True
    assert summary["capability_summary"]["capability_id"] == "example.capability"


def test_developer_workflow_control_summary_cases() -> None:
    summary = developer_workflow_control_summary(
        {
            "ready_for_external_pr_execution": False,
            "external_approval_status": "pending",
            "command_preview_rendered": False,
            "first_next_evidence": "",
            "local_candidate_ready": True,
            "pr_tool_admitted": True,
            "sandbox_receipts_completed": 4,
            "sandbox_receipts_required": 4,
            "next_evidence": ["external_approval_witness", "command_preview"],
            "rollback_required": True,
        }
    )

    assert summary["contract_id"] == "operator_dashboard_control_summary.v1"
    assert summary["summary_id"] == "developer_workflow_control_summary.v1"
    assert summary["operator_message"] == (
        "Action needed before PR execution: provide external_approval_witness; "
        "external approval is pending."
    )
    assert summary["action_banner"] == summary["operator_message"]
    assert summary["capability_id"] == "mullu_developer_workflow.v1"
    assert summary["mode"] == "lab"
    assert summary["current_level"] == "L4"
    assert summary["next_level"] == "L5"
    assert summary["status"] == "approval_required"
    assert summary["blocked_reason"] == "external approval pending"
    assert summary["next_unlock"] == "external_approval_witness"
    assert summary["next_evidence_count"] == 2
    assert summary["external_effects_allowed"] is False
    assert summary["rollback_required"] is True
    assert summary["capability_summary"]["next_evidence"] == ["external_approval_witness", "command_preview"]


def test_operator_control_tower_projects_rollback_receipt_visibility() -> None:
    gate = build_software_dev_capability_admission_gate(clock=_clock)
    store = SoftwareChangeReceiptStore()
    store.append(_receipt("software-receipt-rollback", SoftwareChangeReceiptStage.ROLLBACK_COMPLETED))
    app = create_gateway_app(
        platform=StubPlatform(),
        capability_admission_gate_override=gate,
        software_receipt_store_override=store,
    )
    client = TestClient(app)

    response = client.get("/operator/control-tower/read-model?domain=software_dev")

    assert response.status_code == 200
    payload = response.json()
    panels = {item["panel"]: item for item in payload["panels"]}
    workflow_run = panels["workflow_monitor"]["metadata"]["developer_workflow_run"]
    assert workflow_run["rollback_receipt_status"] == "available"
    assert workflow_run["rollback_receipt_count"] == 1
    assert workflow_run["rollback_receipt_refs"] == ["software-change-receipt:software-receipt-rollback"]


def test_operator_control_tower_projects_receipt_checklist_completion() -> None:
    gate = build_software_dev_capability_admission_gate(clock=_clock)
    store = SoftwareChangeReceiptStore()
    store.append(_receipt("software-receipt-patch", SoftwareChangeReceiptStage.PATCH_APPLIED))
    store.append(_receipt("software-receipt-gate", SoftwareChangeReceiptStage.GATE_EVALUATED))
    store.append(_receipt("software-receipt-terminal", SoftwareChangeReceiptStage.TERMINAL_CLOSED))
    app = create_gateway_app(
        platform=StubPlatform(),
        capability_admission_gate_override=gate,
        software_receipt_store_override=store,
    )
    client = TestClient(app)

    response = client.get("/operator/control-tower/read-model?domain=software_dev")

    assert response.status_code == 200
    payload = response.json()
    panels = {item["panel"]: item for item in payload["panels"]}
    checklist = panels["workflow_monitor"]["metadata"]["developer_workflow_run"]["receipt_checklist"]
    checklist_by_id = {item["checklist_id"]: item for item in checklist}
    assert checklist_by_id["sandbox_patch_receipt"]["status"] == "complete"
    assert checklist_by_id["test_gate_receipt"]["status"] == "complete"
    assert checklist_by_id["diff_review_receipt"]["status"] == "complete"
    assert checklist_by_id["terminal_receipt"]["status"] == "complete"
    assert checklist_by_id["operator_approval"]["status"] == "pending"
    assert panels["workflow_monitor"]["metadata"]["developer_workflow_run"][
        "receipt_checklist_completed_required_count"
    ] == 4
    readiness = panels["workflow_monitor"]["metadata"]["developer_workflow_run"]["sandbox_to_pr_readiness"]
    assert readiness["readiness_status"] == "awaiting_operator_approval"
    assert readiness["receipt_checklist_ready"] is True
    assert readiness["receipt_checklist_completed_count"] == 4
    assert readiness["operator_approval_status"] == "pending"
    assert readiness["pr_candidate_status"] == "pending"
    assert readiness["rollback_receipt_status"] == "not_recorded"
    assert readiness["next_action"] == "request operator approval for PR candidate"
    packet = panels["workflow_monitor"]["metadata"]["sandbox_to_pr_packet"]
    focus = panels["workflow_monitor"]["metadata"]["sandbox_to_pr_focus"]
    assert packet["status"] == "awaiting_operator_approval"
    assert packet["blocker"] == "operator_approval_missing"
    assert packet["receipts"]["ready"] is True
    assert packet["receipts"]["completed_count"] == 4
    assert packet["approval"]["status"] == "pending"
    assert all(item["status"] == "complete" for item in packet["next_evidence"])
    assert focus["focus_id"] == "operator_approval"
    assert focus["label"] == "Operator approval"
    assert focus["status"] == "pending"
    assert focus["action"] == "request operator approval for PR candidate"
    assert focus["blocker"] == "operator_approval_missing"
    assert focus["next_action"] == "request operator approval for PR candidate"
    assert focus["source"] == "workflow_monitor.metadata.developer_workflow_run.receipt_checklist.operator_approval"
    evidence = {item["evidence_id"]: item for item in packet["required_evidence"]}
    assert evidence["sandbox_receipts"]["status"] == "complete"
    assert evidence["operator_approval"]["status"] == "pending"

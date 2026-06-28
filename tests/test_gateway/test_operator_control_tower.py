"""Gateway operator control tower tests.

Purpose: verify unified operator panel aggregation, missing-panel signaling,
review/block signaling, raw surface blocking, and schema contract behavior.
Governance scope: read-only operator visibility across production operations.
Dependencies: gateway.operator_control_tower and its public JSON schema.
Invariants:
  - Every required operator panel appears in the snapshot.
  - Missing panels emit bounded warning signals.
  - Raw tool surfaces emit critical signals and remain unexposed.
  - Snapshot output is schema-valid and hash-bearing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from gateway.operator_control_tower import (
    OperatorControlTowerBuilder,
    OperatorPanelKind,
    OperatorSignalSeverity,
    OperatorTowerSignal,
    PanelHealth,
    operator_control_tower_snapshot_to_json_dict,
    operator_control_tower_status_receipt,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "operator_control_tower_snapshot.schema.json"
STATUS_RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "operator_control_tower_status_receipt.schema.json"
NOW = "2026-05-06T12:00:00Z"


def test_control_tower_builds_all_required_panels_when_sources_are_attached() -> None:
    builder = _full_builder()
    snapshot = builder.build(tenant_id="tenant-a", generated_at=NOW)
    panel_names = {panel.panel for panel in snapshot.panels}

    assert snapshot.panel_count == len(OperatorPanelKind)
    assert panel_names == set(OperatorPanelKind)
    assert snapshot.overall_health is PanelHealth.OK
    assert snapshot.missing_panel_count == 0
    assert snapshot.degraded_panel_count == 0
    assert snapshot.critical_signal_count == 0
    assert snapshot.raw_tool_surface_exposed is False
    assert snapshot.snapshot_hash


def test_missing_panels_emit_bounded_warning_signals() -> None:
    builder = OperatorControlTowerBuilder()
    builder.attach_panel(OperatorPanelKind.LIVE_RUNS, _read_model("runs", item_count=3))
    snapshot = builder.build(tenant_id="tenant-a", generated_at=NOW)

    assert snapshot.overall_health is PanelHealth.MISSING
    assert snapshot.missing_panel_count == len(OperatorPanelKind) - 1
    assert len(snapshot.signals) == len(OperatorPanelKind) - 1
    assert all(signal.severity is OperatorSignalSeverity.WARNING for signal in snapshot.signals)
    assert all(signal.reason == "panel_read_model_missing" for signal in snapshot.signals)


def test_review_and_blocked_items_degrade_panel_and_emit_signal() -> None:
    builder = _full_builder()
    builder.attach_panel(
        OperatorPanelKind.APPROVALS,
        _read_model("approvals", item_count=4, blocked_count=1, review_count=2, evidence_refs=("case:approval-1",)),
    )
    snapshot = builder.build(tenant_id="tenant-a", generated_at=NOW)
    approvals = next(panel for panel in snapshot.panels if panel.panel is OperatorPanelKind.APPROVALS)
    approval_signal = next(signal for signal in snapshot.signals if signal.panel is OperatorPanelKind.APPROVALS)

    assert snapshot.overall_health is PanelHealth.DEGRADED
    assert snapshot.degraded_panel_count == 1
    assert approvals.health is PanelHealth.DEGRADED
    assert approvals.blocked_count == 1
    assert approvals.review_count == 2
    assert approval_signal.reason == "operator_review_or_blocked_items_present"
    assert "case:approval-1" in approval_signal.evidence_refs


def test_read_model_evidence_refs_reject_structured_values() -> None:
    builder = _full_builder()
    builder.attach_panel(
        OperatorPanelKind.APPROVALS,
        _read_model("approvals", item_count=4, blocked_count=1, evidence_refs=("case:approval-1",))
        | {"evidence_refs": [{"ref": "case:approval-1"}]},
    )

    snapshot = builder.build(tenant_id="tenant-a", generated_at=NOW)
    approvals = next(panel for panel in snapshot.panels if panel.panel is OperatorPanelKind.APPROVALS)
    approval_signal = next(signal for signal in snapshot.signals if signal.panel is OperatorPanelKind.APPROVALS)

    assert approvals.evidence_refs == ()
    assert approval_signal.evidence_refs == ()
    assert approval_signal.reason == "operator_review_or_blocked_items_present"


def test_signal_evidence_refs_reject_non_string_values() -> None:
    with pytest.raises(ValueError, match="evidence_refs_invalid"):
        OperatorTowerSignal(
            signal_id="signal-1",
            panel=OperatorPanelKind.APPROVALS,
            severity=OperatorSignalSeverity.WARNING,
            reason="operator_review_or_blocked_items_present",
            evidence_refs=(1,),  # type: ignore[arg-type]
        )


def test_raw_tool_surface_is_not_exposed_and_raises_critical_signal() -> None:
    builder = _full_builder()
    builder.attach_panel(
        OperatorPanelKind.CAPABILITY_HEALTH,
        {
            **_read_model("capability", item_count=7),
            "raw_tool_surface_exposed": True,
            "metadata": {"secret": "redacted", "visible": "yes"},
        },
    )
    snapshot = builder.build(tenant_id="tenant-a", generated_at=NOW)
    capability = next(panel for panel in snapshot.panels if panel.panel is OperatorPanelKind.CAPABILITY_HEALTH)
    signal = next(signal for signal in snapshot.signals if signal.panel is OperatorPanelKind.CAPABILITY_HEALTH)

    assert snapshot.raw_tool_surface_exposed is False
    assert snapshot.critical_signal_count == 1
    assert snapshot.overall_health is PanelHealth.DEGRADED
    assert capability.health is PanelHealth.DEGRADED
    assert capability.metadata == {"visible": "yes"}
    assert signal.severity is OperatorSignalSeverity.CRITICAL
    assert signal.reason == "raw_operator_surface_exposed"


def test_snapshot_rejects_raw_surface_true() -> None:
    builder = _full_builder()
    snapshot = builder.build(tenant_id="tenant-a", generated_at=NOW)

    with pytest.raises(ValueError, match="raw_tool_surface_must_not_be_exposed"):
        type(snapshot)(**{**snapshot.to_json_dict(), "panels": snapshot.panels, "signals": snapshot.signals, "raw_tool_surface_exposed": True})


def test_operator_control_tower_snapshot_schema_exposes_panel_contract() -> None:
    builder = _full_builder()
    snapshot = builder.build(tenant_id="tenant-a", generated_at=NOW)
    payload = operator_control_tower_snapshot_to_json_dict(snapshot)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    Draft202012Validator(schema).validate(payload)
    assert set(schema["required"]).issubset(payload)
    assert schema["$id"] == "urn:mullusi:schema:operator-control-tower-snapshot:1"
    assert "approval" not in schema["$defs"]["panel"]["enum"]
    assert "approvals" in schema["$defs"]["panel"]["enum"]
    assert payload["raw_tool_surface_exposed"] is False
    assert snapshot.snapshot_hash


def test_operator_control_tower_status_receipt_is_projection_only() -> None:
    builder = _full_builder()
    builder.attach_panel(
        OperatorPanelKind.CAPABILITY_HEALTH,
        _read_model("capability_friction_control", item_count=6)
        | {
            "metadata": {
                "developer_workflow_summary": {
                    "task": "Mullu Developer Workflow v1",
                    "status": "preflight_ready",
                    "reason": "local lab workflow can prepare sandbox diff",
                    "next_unlock": "approval",
                    "action_needed": "attach sandbox receipts",
                },
            },
        },
    )
    builder.attach_panel(
        OperatorPanelKind.WORKFLOW_MONITOR,
        _read_model("operator_workflow_monitor", item_count=1)
        | {
            "metadata": {
                "sandbox_to_pr_packet": {
                    "status": "awaiting_receipts",
                    "blocker": "sandbox_receipts_incomplete",
                    "next_action": "complete sandbox patch, test, diff, and terminal receipts",
                },
                "sandbox_to_pr_focus": {
                    "focus_id": "sandbox_patch_receipt",
                    "label": "Sandbox patch receipt",
                    "status": "pending",
                    "action": "attach before state, after state, diff, command, and rollback receipt",
                    "source": "workflow_monitor.metadata.developer_workflow_run.receipt_checklist.sandbox_patch_receipt",
                    "next_action": "complete sandbox patch, test, diff, and terminal receipts",
                    "blocker": "sandbox_receipts_incomplete",
                },
                "sandbox_receipt_attachment_packet": {
                    "packet_id": "developer_workflow_sandbox_receipt_attachment_packet.v1",
                    "packet_status": "awaiting_attachments",
                    "external_effects_allowed": False,
                    "completed_count": 1,
                    "required_count": 4,
                    "next_attachment": {
                        "receipt_id": "test_gate_receipt",
                        "label": "Test gate receipt",
                        "status": "awaiting_attachment",
                        "action": "attach bounded local test command receipt and observed result",
                    },
                    "attachments": [
                        {
                            "receipt_id": "sandbox_patch_receipt",
                            "label": "Sandbox patch receipt",
                            "status": "attached",
                            "stage": "write_files_in_sandbox",
                            "action": "attach before state, after state, diff, command, and rollback receipt",
                            "source": (
                                "workflow_monitor.metadata.developer_workflow_run.receipt_checklist."
                                "sandbox_patch_receipt"
                            ),
                            "evidence_refs": ["proof://developer-workflow-v1/sandbox-patch/collected"],
                        },
                    ],
                },
                "local_sandbox_proof_report": {
                    "status": "attached",
                    "ok": True,
                    "bundle_status": "awaiting_receipts",
                    "attachment_packet_status": "awaiting_attachments",
                    "next_attachment_id": "test_gate_receipt",
                    "pr_readiness_status": "awaiting_sandbox_receipts",
                    "completed_count": 1,
                    "required_count": 4,
                    "execution_performed": False,
                    "external_effects_allowed": False,
                    "generated_artifacts": {
                        "sandbox_receipt_attachment_packet": (
                            ".change_assurance/"
                            "developer_workflow_sandbox_receipt_attachment_packet.generated.json"
                        )
                    },
                },
                "local_rollback_summary_packet": {
                    "status": "attached",
                    "packet_status": "rollback_ready",
                    "generated_artifact_count": 1,
                    "rollback_execution_performed": False,
                    "external_effects_allowed": False,
                    "artifacts": [
                        {
                            "artifact_id": "sandbox_receipt_attachment_packet",
                            "path": (
                                ".change_assurance/"
                                "developer_workflow_sandbox_receipt_attachment_packet.generated.json"
                            ),
                            "rollback_command": (
                                "Remove-Item -LiteralPath "
                                "'.change_assurance/developer_workflow_sandbox_receipt_attachment_packet.generated.json' "
                                "-Force"
                            ),
                            "required_confirmation": True,
                        }
                    ],
                },
                "local_rollback_approval_packet": {
                    "status": "attached",
                    "packet_status": "approval_recorded",
                    "approval_status": "approved",
                    "approval_scope": "selected_artifacts",
                    "selected_artifact_count": 1,
                    "delete_execution_allowed": True,
                    "rollback_execution_performed": False,
                    "external_effects_allowed": False,
                    "authorized_artifacts": [
                        {
                            "artifact_id": "sandbox_receipt_attachment_packet",
                            "path": (
                                ".change_assurance/"
                                "developer_workflow_sandbox_receipt_attachment_packet.generated.json"
                            ),
                            "rollback_command": (
                                "Remove-Item -LiteralPath "
                                "'.change_assurance/developer_workflow_sandbox_receipt_attachment_packet.generated.json' "
                                "-Force"
                            ),
                            "approval_status": "approved",
                            "execution_allowed": True,
                            "required_confirmation": True,
                        }
                    ],
                },
                "local_rollback_execution_receipt": {
                    "status": "attached",
                    "execution_status": "rollback_executed",
                    "execution_mode": "execute",
                    "rollback_execution_performed": True,
                    "external_effects_allowed": False,
                    "target_path_checks_performed": True,
                    "selected_artifact_count": 1,
                    "executed_artifact_count": 1,
                    "skipped_artifact_count": 0,
                    "failed_artifact_count": 0,
                    "artifacts": [
                        {
                            "artifact_id": "sandbox_receipt_attachment_packet",
                            "path": (
                                ".change_assurance/"
                                "developer_workflow_sandbox_receipt_attachment_packet.generated.json"
                            ),
                            "resolved_path": (
                                "C:/repo/.change_assurance/"
                                "developer_workflow_sandbox_receipt_attachment_packet.generated.json"
                            ),
                            "action_status": "deleted",
                            "path_within_workspace": True,
                            "pre_exists": True,
                            "post_exists": False,
                            "error_message": "",
                        }
                    ],
                },
                "local_rollback_flow_command": {
                    "status": "ready",
                    "action_label": "Run local rollback dry-run",
                    "next_action": "run dry-run rollback flow and inspect execution receipt before adding --execute",
                    "command": (
                        "python scripts/run_developer_workflow_local_rollback_flow.py "
                        "--rollback-summary "
                        ".change_assurance/developer_workflow_local_rollback_summary_packet.generated.json "
                        "--artifact-id 'sandbox_receipt_attachment_packet' "
                        "--approved-by operator "
                        "--approval-evidence-ref approval://local/rollback-flow/operator-command "
                        "--json"
                    ),
                    "execute_command": (
                        "python scripts/run_developer_workflow_local_rollback_flow.py "
                        "--rollback-summary "
                        ".change_assurance/developer_workflow_local_rollback_summary_packet.generated.json "
                        "--artifact-id 'sandbox_receipt_attachment_packet' "
                        "--approved-by operator "
                        "--approval-evidence-ref approval://local/rollback-flow/operator-command "
                        "--json --execute"
                    ),
                    "selected_artifact_ids": ["sandbox_receipt_attachment_packet"],
                    "rollback_summary_path": (
                        ".change_assurance/developer_workflow_local_rollback_summary_packet.generated.json"
                    ),
                    "approval_packet_path": (
                        ".change_assurance/developer_workflow_local_rollback_approval_packet.generated.json"
                    ),
                    "dry_run_receipt_path": (
                        ".change_assurance/developer_workflow_local_rollback_execution_receipt.generated.json"
                    ),
                    "execution_receipt_path": (
                        ".change_assurance/developer_workflow_local_rollback_execution_receipt.generated.json"
                    ),
                    "rollback_summary_href": "/operator/control-tower/local-rollback-receipt?receipt_id=summary",
                    "approval_packet_href": "/operator/control-tower/local-rollback-receipt?receipt_id=approval",
                    "dry_run_receipt_href": "/operator/control-tower/local-rollback-receipt?receipt_id=execution",
                    "execution_receipt_href": "/operator/control-tower/local-rollback-receipt?receipt_id=execution",
                    "receipt_availability": {
                        "summary": "available",
                        "approval": "available",
                        "execution": "available",
                        "available_count": 3,
                        "required_count": 3,
                    },
                    "readiness_verdict": "ready_for_dry_run",
                    "dry_run_required": True,
                    "execution_requires_execute_flag": True,
                    "external_effects_allowed": False,
                },
                "pr_readiness_bundle": {
                    "bundle_id": "pr_readiness_bundle.v1",
                    "readiness_status": "awaiting_sandbox_receipts",
                    "ready_for_external_pr_execution": False,
                    "first_blocker": "sandbox_receipts",
                    "next_evidence": ["sandbox_receipts", "approval_packet"],
                },
                "developer_workflow_operator_receipt": {
                    "receipt_id": "developer_workflow_operator_receipt.v1",
                    "schema_ref": "schemas/developer_workflow_operator_receipt.schema.json",
                    "solver_outcome": "AwaitingEvidence",
                    "readiness_status": "awaiting_sandbox_receipts",
                    "execution_performed": False,
                    "ready_for_external_pr_execution": False,
                    "command_preview_rendered": False,
                    "next_evidence": ["sandbox_receipts", "approval_packet"],
                    "receipt_hash": "a" * 64,
                },
                "developer_workflow_run": {
                    "status": "waiting_for_approval",
                    "current_task_id": "sandbox_change",
                    "receipt_checklist_required_count": 6,
                    "receipt_checklist_completed_required_count": 0,
                    "rollback_receipt_status": "not_recorded",
                    "sandbox_receipt_bundle_status": "awaiting_receipts",
                    "sandbox_receipt_bundle_completed_count": 1,
                    "sandbox_receipt_bundle_required_count": 4,
                    "sandbox_receipt_bundle_receipts": [
                        {
                            "receipt_id": "sandbox_patch_receipt",
                            "label": "Sandbox patch receipt",
                            "status": "complete",
                            "stage": "write_files_in_sandbox",
                            "required": True,
                            "source": "workflow_monitor.metadata.developer_workflow_run.receipt_checklist.sandbox_patch_receipt",
                            "evidence_refs": ["proof://developer-workflow-v1/sandbox-patch/collected"],
                        },
                        {
                            "receipt_id": "test_gate_receipt",
                            "label": "Test gate receipt",
                            "status": "pending",
                            "stage": "run_tests",
                            "required": True,
                            "source": "workflow_monitor.metadata.developer_workflow_run.receipt_checklist.test_gate_receipt",
                            "evidence_refs": [],
                        },
                    ],
                },
            },
        },
    )
    snapshot = builder.build(tenant_id="tenant-a", generated_at=NOW)

    receipt = operator_control_tower_status_receipt(snapshot)
    second_receipt = operator_control_tower_status_receipt(snapshot)
    schema = json.loads(STATUS_RECEIPT_SCHEMA_PATH.read_text(encoding="utf-8"))

    Draft202012Validator(schema).validate(receipt)
    assert receipt == second_receipt
    assert receipt["receipt_type"] == "operator_control_tower_status_receipt.v1"
    assert receipt["projection_only"] is True
    assert receipt["external_effects_allowed"] is False
    assert receipt["receipt_id"].startswith("operator-control-tower-status-")
    assert len(receipt["receipt_hash"]) >= 32
    assert receipt["sandbox_to_pr"]["focus"]["focus_id"] == "sandbox_patch_receipt"
    assert receipt["sandbox_to_pr"]["focus"]["action"] == (
        "attach before state, after state, diff, command, and rollback receipt"
    )
    assert receipt["sandbox_to_pr"]["blocker"] == "sandbox_receipts_incomplete"
    assert receipt["pr_readiness"]["bundle_id"] == "pr_readiness_bundle.v1"
    assert receipt["pr_readiness"]["readiness_status"] == "awaiting_sandbox_receipts"
    assert receipt["pr_readiness"]["ready_for_external_pr_execution"] is False
    assert receipt["pr_readiness"]["first_blocker"] == "sandbox_receipts"
    assert receipt["pr_readiness"]["next_evidence"] == ["sandbox_receipts", "approval_packet"]
    assert receipt["developer_workflow_operator_receipt"]["receipt_id"] == "developer_workflow_operator_receipt.v1"
    assert receipt["developer_workflow_operator_receipt"]["solver_outcome"] == "AwaitingEvidence"
    assert receipt["developer_workflow_operator_receipt"]["execution_performed"] is False
    assert receipt["developer_workflow_operator_receipt"]["command_preview_rendered"] is False
    assert receipt["developer_workflow_operator_receipt"]["receipt_hash"] == "a" * 64
    assert receipt["sandbox_receipt_bundle"]["status"] == "awaiting_receipts"
    assert receipt["sandbox_receipt_bundle"]["completed_count"] == 1
    assert receipt["sandbox_receipt_bundle"]["required_count"] == 4
    assert receipt["sandbox_receipt_bundle"]["receipts"][0]["receipt_id"] == "sandbox_patch_receipt"
    assert receipt["sandbox_receipt_bundle"]["receipts"][0]["evidence_refs"] == [
        "proof://developer-workflow-v1/sandbox-patch/collected"
    ]
    assert receipt["sandbox_receipt_attachments"]["packet_status"] == "awaiting_attachments"
    assert receipt["sandbox_receipt_attachments"]["completed_count"] == 1
    assert receipt["sandbox_receipt_attachments"]["required_count"] == 4
    assert receipt["sandbox_receipt_attachments"]["next_attachment"]["receipt_id"] == "test_gate_receipt"
    assert receipt["sandbox_receipt_attachments"]["attachments"][0]["status"] == "attached"
    assert receipt["sandbox_receipt_attachments"]["attachments"][0]["evidence_refs"] == [
        "proof://developer-workflow-v1/sandbox-patch/collected"
    ]
    assert receipt["local_sandbox_proof_report"]["status"] == "attached"
    assert receipt["local_sandbox_proof_report"]["ok"] is True
    assert receipt["local_sandbox_proof_report"]["attachment_packet_status"] == "awaiting_attachments"
    assert receipt["local_sandbox_proof_report"]["next_attachment_id"] == "test_gate_receipt"
    assert receipt["local_sandbox_proof_report"]["execution_performed"] is False
    assert receipt["local_sandbox_proof_report"]["external_effects_allowed"] is False
    assert (
        receipt["local_sandbox_proof_report"]["generated_artifacts"]["sandbox_receipt_attachment_packet"]
        == ".change_assurance/developer_workflow_sandbox_receipt_attachment_packet.generated.json"
    )
    assert receipt["local_rollback_summary_packet"]["status"] == "attached"
    assert receipt["local_rollback_summary_packet"]["packet_status"] == "rollback_ready"
    assert receipt["local_rollback_summary_packet"]["generated_artifact_count"] == 1
    assert receipt["local_rollback_summary_packet"]["rollback_execution_performed"] is False
    assert receipt["local_rollback_summary_packet"]["external_effects_allowed"] is False
    assert receipt["local_rollback_summary_packet"]["artifacts"][0]["required_confirmation"] is True
    assert "Remove-Item -LiteralPath" in receipt["local_rollback_summary_packet"]["artifacts"][0]["rollback_command"]
    assert receipt["local_rollback_approval_packet"]["status"] == "attached"
    assert receipt["local_rollback_approval_packet"]["packet_status"] == "approval_recorded"
    assert receipt["local_rollback_approval_packet"]["approval_status"] == "approved"
    assert receipt["local_rollback_approval_packet"]["delete_execution_allowed"] is True
    assert receipt["local_rollback_approval_packet"]["rollback_execution_performed"] is False
    assert receipt["local_rollback_approval_packet"]["external_effects_allowed"] is False
    assert receipt["local_rollback_approval_packet"]["authorized_artifacts"][0]["execution_allowed"] is True
    assert receipt["local_rollback_execution_receipt"]["status"] == "attached"
    assert receipt["local_rollback_execution_receipt"]["execution_status"] == "rollback_executed"
    assert receipt["local_rollback_execution_receipt"]["execution_mode"] == "execute"
    assert receipt["local_rollback_execution_receipt"]["rollback_execution_performed"] is True
    assert receipt["local_rollback_execution_receipt"]["external_effects_allowed"] is False
    assert receipt["local_rollback_execution_receipt"]["target_path_checks_performed"] is True
    assert receipt["local_rollback_execution_receipt"]["artifacts"][0]["action_status"] == "deleted"
    assert receipt["local_rollback_flow_command"]["status"] == "ready"
    assert receipt["local_rollback_flow_command"]["action_label"] == "Run local rollback dry-run"
    assert receipt["local_rollback_flow_command"]["next_action"] == (
        "run dry-run rollback flow and inspect execution receipt before adding --execute"
    )
    assert receipt["local_rollback_flow_command"]["selected_artifact_ids"] == ["sandbox_receipt_attachment_packet"]
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
        "summary": "available",
        "approval": "available",
        "execution": "available",
        "available_count": 3,
        "required_count": 3,
    }
    assert receipt["local_rollback_flow_command"]["readiness_verdict"] == "ready_for_dry_run"
    assert "run_developer_workflow_local_rollback_flow.py" in receipt["local_rollback_flow_command"]["command"]
    assert "--execute" not in receipt["local_rollback_flow_command"]["command"]
    assert receipt["local_rollback_flow_command"]["execute_command"].endswith("--json --execute")
    assert receipt["local_rollback_flow_command"]["dry_run_required"] is True
    assert receipt["local_rollback_flow_command"]["execution_requires_execute_flag"] is True
    assert receipt["local_rollback_flow_command"]["external_effects_allowed"] is False
    assert receipt["workflow_run"]["rollback_receipt_status"] == "not_recorded"
    assert receipt["snapshot_hash"] == snapshot.snapshot_hash
    assert receipt["source_refs"]["pr_readiness"] == "workflow_monitor.metadata.pr_readiness_bundle"
    assert (
        receipt["source_refs"]["sandbox_receipt_attachments"]
        == "workflow_monitor.metadata.sandbox_receipt_attachment_packet"
    )
    assert (
        receipt["source_refs"]["local_sandbox_proof_report"]
        == "workflow_monitor.metadata.local_sandbox_proof_report"
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
        receipt["source_refs"]["local_rollback_flow_command"]
        == "workflow_monitor.metadata.local_rollback_flow_command"
    )
    assert (
        receipt["source_refs"]["developer_workflow_operator_receipt"]
        == "workflow_monitor.metadata.developer_workflow_operator_receipt"
    )


def _full_builder() -> OperatorControlTowerBuilder:
    builder = OperatorControlTowerBuilder()
    for panel in OperatorPanelKind:
        builder.attach_panel(panel, _read_model(panel.value, item_count=1))
    return builder


def _read_model(
    source_surface: str,
    *,
    item_count: int,
    blocked_count: int = 0,
    review_count: int = 0,
    evidence_refs: tuple[str, ...] = ("witness:ok",),
) -> dict[str, object]:
    return {
        "source_surface": source_surface,
        "item_count": item_count,
        "freshness_seconds": 30,
        "signal_count": 0,
        "blocked_count": blocked_count,
        "review_count": review_count,
        "evidence_refs": evidence_refs,
        "raw_tool_surface_exposed": False,
        "metadata": {"owner": "operator"},
    }

"""Tests for the operator workflow next-action packet.

Purpose: prove the next-action handoff packet is derived from the validated
operator dashboard readiness lane without granting execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.build_operator_workflow_next_action_packet and
gateway.operator_workflow_dashboard.
Invariants: packet output is schema-backed, projection-only, and blocks live
execution, approval performance, and external effects.
"""

from __future__ import annotations

import json
from pathlib import Path

from gateway.operator_workflow_dashboard import build_operator_workflow_dashboard_read_model
from scripts.build_developer_workflow_operator_receipt import canonical_hash
from scripts.build_operator_local_developer_workflow_receipt_read_model import (
    build_operator_local_developer_workflow_receipt_read_model,
)
from scripts.build_operator_workflow_next_action_packet import (
    build_operator_workflow_next_action_packet,
    main,
    validate_operator_workflow_next_action_packet,
)
from scripts.validate_operator_control_tower_status_receipt import build_default_operator_control_tower_status_receipt


def _operator_receipt() -> dict[str, object]:
    receipt: dict[str, object] = {
        "receipt_id": "developer_workflow_operator_receipt.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": "operator_workflow_next_action_packet_test",
        "solver_outcome": "AwaitingEvidence",
        "execution_boundary": "local_lab_to_external_pr_preview",
        "execution_performed": False,
        "readiness_status": "awaiting_external_pr_approval",
        "sandbox_receipts": {
            "bundle_status": "complete",
            "completed_count": 4,
            "required_count": 4,
            "bundle_hash": "a" * 64,
        },
        "approvals": {
            "pr_preparation": {"status": "approved", "ready": True},
            "external_pr_execution": {"status": "pending", "ready": False},
        },
        "local_pr_candidate": {
            "candidate_status": "ready",
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
            "evidence_refs": ["proof://rollback"],
            "commands": ["git push origin --delete codex/developer-workflow-local-candidate"],
        },
        "source_refs": {
            "sandbox_receipt_bundle_path": "examples/developer_workflow_sandbox_receipt_bundle.foundation.json",
            "approval_packet_path": "examples/pr_preparation_approval_packet.foundation.json",
            "local_candidate_packet_path": "examples/local_pr_candidate_packet.foundation.json",
            "pr_tool_admission_packet_path": "examples/pr_tool_admission_packet.foundation.json",
            "external_approval_witness_path": "examples/external_pr_execution_approval_witness.foundation.json",
            "command_preview_packet_path": "examples/pr_command_preview_packet.foundation.json",
            "metadata_packet_path": "examples/pr_metadata_packet.foundation.json",
            "pr_readiness_bundle_path": "examples/pr_readiness_bundle.foundation.json",
            "receipt_builder": "python scripts/build_developer_workflow_operator_receipt.py",
        },
        "receipt_hash": "",
    }
    receipt["receipt_hash"] = canonical_hash(receipt)
    return receipt


def _local_workflow_receipt() -> dict[str, object]:
    return build_operator_local_developer_workflow_receipt_read_model(
        operator_receipt=_operator_receipt(),
        operator_receipt_source_ref="operator-receipt.json",
        control_tower_status_receipt=build_default_operator_control_tower_status_receipt(),
        control_tower_source_ref="control-tower-status.json",
    )


def _dashboard() -> dict[str, object]:
    return build_operator_workflow_dashboard_read_model(
        local_workflow_receipt=_local_workflow_receipt(),
        local_workflow_source_ref="local-workflow-receipt.json",
    )


def test_operator_workflow_next_action_packet_builds_from_dashboard_readiness_lane(tmp_path: Path) -> None:
    dashboard_path = tmp_path / "operator-workflow-dashboard.json"
    packet = build_operator_workflow_next_action_packet(
        dashboard=_dashboard(),
        dashboard_path=dashboard_path,
    )
    validation = validate_operator_workflow_next_action_packet(packet=packet)

    assert validation.ok is True
    assert packet["packet_id"] == "operator_workflow_next_action_packet.foundation.v1"
    assert packet["source_dashboard_id"] == "operator_workflow_dashboard.foundation.v1"
    assert packet["task"] == "Mullu Developer Workflow v1"
    assert packet["lane_status"] == "awaiting_closure_packet"
    assert packet["operator_outcome"] == "AwaitingEvidence"
    assert packet["primary_blocker"] == "local_workflow_closure_packet"
    assert packet["current_gate_id"] == "test_gate"
    assert packet["next_action"] == "run local workflow closure packet builder"
    assert packet["linked_receipts"] == {
        "closure_packet": False,
        "safe_local_action_rehearsal": False,
        "causal_repair": False,
    }
    assert packet["readiness_is_not_execution_authority"] is True
    assert packet["projection_only"] is True
    assert packet["execution_authority_granted"] is False
    assert packet["execution_performed"] is False
    assert packet["live_execution_enabled"] is False
    assert packet["external_effects_allowed"] is False
    assert packet["approval"]["performed"] is False


def test_operator_workflow_next_action_packet_rejects_authority_overclaim(tmp_path: Path) -> None:
    packet = build_operator_workflow_next_action_packet(
        dashboard=_dashboard(),
        dashboard_path=tmp_path / "operator-workflow-dashboard.json",
    )
    packet["projection_only"] = False
    packet["execution_authority_granted"] = True
    packet["live_execution_enabled"] = True
    packet["approval"]["performed"] = True

    validation = validate_operator_workflow_next_action_packet(packet=packet)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "projection_only_must_be_true" in serialized_errors
    assert "execution_authority_granted_must_be_false" in serialized_errors
    assert "live_execution_enabled_must_be_false" in serialized_errors
    assert "approval_performed_must_be_false" in serialized_errors
    assert "packet_hash_mismatch" in serialized_errors


def test_operator_workflow_next_action_packet_cli_writes_json(tmp_path: Path, capsys) -> None:
    dashboard_path = tmp_path / "operator-workflow-dashboard.json"
    output_path = tmp_path / "operator-workflow-next-action-packet.json"
    dashboard_path.write_text(json.dumps(_dashboard()), encoding="utf-8")

    exit_code = main([
        "--dashboard",
        str(dashboard_path),
        "--output",
        str(output_path),
        "--json",
    ])
    captured = capsys.readouterr()
    packet = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert packet["packet_id"] == "operator_workflow_next_action_packet.foundation.v1"
    assert packet["lane_status"] == "awaiting_closure_packet"
    assert packet["execution_performed"] is False
    assert '"operator_workflow_next_action_packet.foundation.v1"' in captured.out


def test_operator_workflow_next_action_packet_cli_rejects_invalid_dashboard(tmp_path: Path, capsys) -> None:
    dashboard_path = tmp_path / "bad-operator-workflow-dashboard.json"
    output_path = tmp_path / "operator-workflow-next-action-packet.json"
    dashboard_path.write_text('{"projection_only": false}\n', encoding="utf-8")

    exit_code = main([
        "--dashboard",
        str(dashboard_path),
        "--output",
        str(output_path),
        "--json",
    ])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert not output_path.exists()
    assert "OPERATOR WORKFLOW NEXT ACTION PACKET INVALID" in captured.out

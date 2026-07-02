"""Tests for safe local action rehearsal.

Purpose: prove local actions can be rehearsed without becoming execution proof
or gaining mutation authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: mcoi.govern.safe_local_action_rehearsal.runner.
Invariants: rehearsal receipts are schema-backed, proof-only, and block live
execution, connector effects, PR creation, merge, and rollback execution.
"""

from __future__ import annotations

import json
from pathlib import Path

from govern.safe_local_action_rehearsal.runner import (
    CAPABILITY_ID,
    FORBIDDEN_EFFECTS,
    build_safe_local_action_rehearsal_receipt,
    run_safe_local_action_rehearsal,
    validate_safe_local_action_rehearsal_receipt,
)
from gateway.operator_workflow_dashboard import build_operator_workflow_dashboard_read_model
from scripts.build_operator_local_developer_workflow_receipt_read_model import (
    build_operator_local_developer_workflow_receipt_read_model,
)
from scripts.build_developer_workflow_operator_receipt import canonical_hash
from scripts.run_safe_local_action_rehearsal import main as run_main
from scripts.validate_safe_local_action_rehearsal import main as validate_main
from scripts.validate_operator_control_tower_status_receipt import build_default_operator_control_tower_status_receipt


def _operator_receipt() -> dict[str, object]:
    receipt: dict[str, object] = {
        "receipt_id": "developer_workflow_operator_receipt.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": "developer_workflow_v1_safe_rehearsal_test",
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


def _dashboard() -> dict[str, object]:
    local_receipt = build_operator_local_developer_workflow_receipt_read_model(
        operator_receipt=_operator_receipt(),
        operator_receipt_source_ref="operator-receipt.json",
        control_tower_status_receipt=build_default_operator_control_tower_status_receipt(),
        control_tower_source_ref="control-tower-status.json",
    )
    return build_operator_workflow_dashboard_read_model(
        local_workflow_receipt=local_receipt,
        local_workflow_source_ref="local-workflow-receipt.json",
    )


def test_safe_local_action_rehearsal_receipt_is_proof_only() -> None:
    receipt = build_safe_local_action_rehearsal_receipt(
        operator_workflow_dashboard=_dashboard(),
        dashboard_source_ref="dashboard.json",
    )
    validation = validate_safe_local_action_rehearsal_receipt(receipt=receipt)

    assert validation.ok is True
    assert receipt["capability_id"] == CAPABILITY_ID
    assert receipt["rehearsal_status"] == "rehearsed_no_effect"
    assert receipt["rehearsal_is_not_execution_proof"] is True
    assert receipt["post_execution_evidence_required"] is True
    assert receipt["live_execution_enabled"] is False
    assert len(receipt["scenarios"]) == 5
    assert all(scenario["proof_only"] is True for scenario in receipt["scenarios"])
    assert all(scenario["mutation_performed"] is False for scenario in receipt["scenarios"])


def test_safe_local_action_rehearsal_blocks_all_live_effects() -> None:
    receipt = build_safe_local_action_rehearsal_receipt(
        operator_workflow_dashboard=_dashboard(),
        dashboard_source_ref="dashboard.json",
    )
    effect_boundary = receipt["effect_boundary"]

    assert all(effect in receipt["blocked_effects"] for effect in FORBIDDEN_EFFECTS)
    assert effect_boundary["file_write_allowed"] is False
    assert effect_boundary["pull_request_create_allowed"] is False
    assert effect_boundary["merge_allowed"] is False
    assert effect_boundary["rollback_execute_allowed"] is False
    assert effect_boundary["connector_call_allowed"] is False
    assert receipt["approval"]["approval_performed"] is False


def test_safe_local_action_rehearsal_validator_rejects_overclaim() -> None:
    receipt = build_safe_local_action_rehearsal_receipt(
        operator_workflow_dashboard=_dashboard(),
        dashboard_source_ref="dashboard.json",
    )
    receipt["rehearsal_is_not_execution_proof"] = False
    receipt["effect_boundary"]["file_write_allowed"] = True
    receipt["scenarios"][0]["mutation_performed"] = True
    receipt["blocked_effects"].remove("merge")

    validation = validate_safe_local_action_rehearsal_receipt(receipt=receipt)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "rehearsal_must_not_claim_execution_proof" in serialized_errors
    assert "effect_boundary_must_be_false:file_write_allowed" in serialized_errors
    assert "scenarios[0].mutation_performed_must_be_false" in serialized_errors
    assert "blocked_effect_missing:merge" in serialized_errors


def test_safe_local_action_rehearsal_run_writes_receipt(tmp_path: Path) -> None:
    output_path = tmp_path / "safe-local-action-rehearsal.json"

    receipt, validation = run_safe_local_action_rehearsal(output_path=output_path)

    assert validation.ok is True
    assert output_path.exists()
    assert receipt["receipt_id"] == "safe_local_action_rehearsal.foundation.v1"
    assert json.loads(output_path.read_text(encoding="utf-8"))["live_execution_enabled"] is False


def test_safe_local_action_rehearsal_cli_and_validator(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "safe-local-action-rehearsal.json"

    run_exit = run_main(["--output", str(output_path), "--json"])
    run_output = capsys.readouterr().out
    validate_exit = validate_main(["--receipt", str(output_path), "--json"])
    validate_output = capsys.readouterr().out

    assert run_exit == 0
    assert validate_exit == 0
    assert '"govern.safe_local_action.rehearsal"' in run_output
    assert '"ok": true' in validate_output

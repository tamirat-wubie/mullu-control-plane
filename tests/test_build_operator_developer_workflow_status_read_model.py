"""Tests for the Developer Workflow operator status read-model builder.

Purpose: prove the compact Developer Workflow status projection is available
without running the gateway server and cannot claim execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.build_operator_developer_workflow_status_read_model.
Invariants: status read models are projection-only and external effects remain
disabled.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_developer_workflow_operator_receipt import canonical_hash
from scripts.build_operator_developer_workflow_status_read_model import (
    build_operator_developer_workflow_status_read_model,
    main,
    validate_operator_developer_workflow_status_read_model,
)


def _operator_receipt(*, readiness_status: str, external_approved: bool) -> dict[str, object]:
    external_ready = readiness_status == "ready_for_external_pr_execution"
    next_evidence = [] if external_ready else ["external_approval_witness", "command_preview"]
    receipt: dict[str, object] = {
        "receipt_id": "developer_workflow_operator_receipt.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": "developer_workflow_v1_status_test",
        "solver_outcome": "SolvedUnverified" if external_ready else "AwaitingEvidence",
        "execution_boundary": "local_lab_to_external_pr_preview",
        "execution_performed": False,
        "readiness_status": readiness_status,
        "sandbox_receipts": {
            "bundle_status": "complete",
            "completed_count": 4,
            "required_count": 4,
            "bundle_hash": "a" * 64,
        },
        "approvals": {
            "pr_preparation": {"status": "approved", "ready": True},
            "external_pr_execution": {"status": "approved" if external_approved else "pending", "ready": external_approved},
        },
        "local_pr_candidate": {
            "candidate_status": "ready",
            "candidate_ready": True,
            "pr_tool_admitted": True,
        },
        "external_handoff": {
            "ready_for_external_pr_execution": external_ready,
            "command_preview_rendered": external_ready,
            "external_effects_allowed": external_ready,
            "pr_creation_allowed": external_ready,
            "branch_push_allowed": external_ready,
        },
        "next_evidence": next_evidence,
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


def test_status_read_model_reports_external_approval_blocker() -> None:
    receipt = _operator_receipt(readiness_status="awaiting_external_pr_approval", external_approved=False)
    read_model = build_operator_developer_workflow_status_read_model(
        receipt=receipt,
        source_ref=".change_assurance/developer_workflow_operator_receipt.generated.json",
    )
    validation = validate_operator_developer_workflow_status_read_model(read_model=read_model)

    assert validation.ok is True
    assert read_model["read_model_id"] == "operator_developer_workflow_status.read_model"
    assert read_model["status"] == "awaiting_external_pr_approval"
    assert read_model["reason"] == "operator external PR approval missing"
    assert read_model["next_unlock"] == "external_approval_witness"
    assert read_model["risk"] == "external repository write"
    assert read_model["action_needed"] == "approve or defer external PR execution"
    assert read_model["summary"]["execution_performed"] is False
    assert read_model["capability_summary"]["status"] == "approval_required"
    assert read_model["capability_summary"]["external_effects_allowed"] is False
    assert read_model["control_summary"]["external_effects_allowed"] is False


def test_status_read_model_keeps_ready_preview_non_executing() -> None:
    receipt = _operator_receipt(readiness_status="ready_for_external_pr_execution", external_approved=True)
    read_model = build_operator_developer_workflow_status_read_model(
        receipt=receipt,
        source_ref=".change_assurance/developer_workflow_operator_receipt.generated.json",
    )
    validation = validate_operator_developer_workflow_status_read_model(read_model=read_model)

    assert validation.ok is True
    assert read_model["status"] == "ready_for_external_pr_execution"
    assert read_model["next_unlock"] == "none"
    assert read_model["summary"]["command_preview_rendered"] is True
    assert read_model["summary"]["execution_performed"] is False
    assert read_model["external_effects_allowed"] is False
    assert read_model["capability_summary"]["status"] == "preflight_ready"
    assert read_model["capability_summary"]["external_effects_allowed"] is False
    assert read_model["control_summary"]["blocked_reason"] == "dashboard execution disabled"


def test_status_read_model_validator_rejects_execution_overclaim() -> None:
    receipt = _operator_receipt(readiness_status="ready_for_external_pr_execution", external_approved=True)
    read_model = build_operator_developer_workflow_status_read_model(receipt=receipt, source_ref="receipt.json")
    read_model["summary"]["execution_performed"] = True

    validation = validate_operator_developer_workflow_status_read_model(read_model=read_model)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "$.summary.execution_performed: expected const False" in serialized_errors
    assert "execution_performed_must_be_false" in serialized_errors
    assert validation.status == "ready_for_external_pr_execution"


def test_status_read_model_cli_writes_json(tmp_path: Path, capsys) -> None:
    receipt_path = tmp_path / "operator-receipt.json"
    output_path = tmp_path / "status-read-model.json"
    receipt_path.write_text(
        json.dumps(_operator_receipt(readiness_status="awaiting_external_pr_approval", external_approved=False)) + "\n",
        encoding="utf-8",
    )

    exit_code = main(["--receipt", str(receipt_path), "--output", str(output_path), "--json"])
    captured = capsys.readouterr()
    read_model = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert read_model["read_model_id"] == "operator_developer_workflow_status.read_model"
    assert read_model["projection_only"] is True
    assert read_model["external_effects_allowed"] is False
    assert read_model["source_ref"] == str(receipt_path)
    assert '"awaiting_external_pr_approval"' in captured.out

"""Tests for the local Developer Workflow receipt read-model builder.

Purpose: prove the operator has one local-lab receipt card that composes
Developer Workflow status and safe-local action without execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.build_operator_local_developer_workflow_receipt_read_model.
Invariants: composed receipt cards are projection-only, acyclic, local-lab
bounded, and block external effects.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_operator_local_developer_workflow_receipt_read_model import (
    FORBIDDEN_EFFECTS,
    build_operator_local_developer_workflow_receipt_read_model,
    main,
    validate_operator_local_developer_workflow_receipt_read_model,
)
from scripts.build_developer_workflow_operator_receipt import canonical_hash
from scripts.validate_operator_control_tower_status_receipt import build_default_operator_control_tower_status_receipt


def _operator_receipt(*, readiness_status: str, external_approved: bool) -> dict[str, object]:
    external_ready = readiness_status == "ready_for_external_pr_execution"
    next_evidence = [] if external_ready else ["external_approval_witness", "command_preview"]
    receipt: dict[str, object] = {
        "receipt_id": "developer_workflow_operator_receipt.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": "developer_workflow_v1_local_card_test",
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
            "external_pr_execution": {
                "status": "approved" if external_approved else "pending",
                "ready": external_approved,
            },
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


def test_local_developer_workflow_receipt_card_composes_status_and_safe_action() -> None:
    read_model = build_operator_local_developer_workflow_receipt_read_model(
        operator_receipt=_operator_receipt(
            readiness_status="awaiting_external_pr_approval",
            external_approved=False,
        ),
        operator_receipt_source_ref="operator-receipt.json",
        control_tower_status_receipt=build_default_operator_control_tower_status_receipt(),
        control_tower_source_ref="control-tower-status.json",
    )
    validation = validate_operator_local_developer_workflow_receipt_read_model(read_model=read_model)

    assert validation.ok is True
    assert read_model["read_model_id"] == "operator_local_developer_workflow_receipt.read_model"
    assert read_model["projection_only"] is True
    assert read_model["execution_performed"] is False
    assert read_model["external_effects_allowed"] is False
    assert read_model["mode"] == "fast_lab"
    assert read_model["status"] == "awaiting_external_pr_approval"
    assert read_model["safe_local_action"]["candidate_id"] == "safe_zone.write_docs"
    assert read_model["safe_local_action"]["execution_boundary"] == "local_lab_only"
    assert read_model["receipt_card"]["execution_performed"] is False
    assert read_model["workflow_status"]["read_model_id"] == "operator_developer_workflow_status.read_model"


def test_local_developer_workflow_receipt_stage_plan_is_acyclic() -> None:
    read_model = build_operator_local_developer_workflow_receipt_read_model(
        operator_receipt=_operator_receipt(
            readiness_status="awaiting_external_pr_approval",
            external_approved=False,
        ),
        operator_receipt_source_ref="operator-receipt.json",
        control_tower_status_receipt=build_default_operator_control_tower_status_receipt(),
        control_tower_source_ref="control-tower-status.json",
    )
    stage_plan = read_model["stage_plan"]
    stage_ids = [stage["stage_id"] for stage in stage_plan]

    assert stage_ids == [
        "request_intake",
        "safe_local_action_selected",
        "sandbox_receipts",
        "test_gate",
        "diff_review",
        "terminal_receipt",
        "approval_handoff",
    ]
    assert stage_plan[0]["predecessors"] == []
    assert stage_plan[-1]["stage_type"] == "approval_gate"
    assert stage_plan[-1]["status"] == "blocked"
    assert all(stage["projection_only"] is True for stage in stage_plan)
    assert all(stage["execution_performed"] is False for stage in stage_plan)
    assert all(stage["external_effects_allowed"] is False for stage in stage_plan)


def test_local_developer_workflow_receipt_forbids_external_effects() -> None:
    read_model = build_operator_local_developer_workflow_receipt_read_model(
        operator_receipt=_operator_receipt(
            readiness_status="ready_for_external_pr_execution",
            external_approved=True,
        ),
        operator_receipt_source_ref="operator-receipt.json",
        control_tower_status_receipt=build_default_operator_control_tower_status_receipt(),
        control_tower_source_ref="control-tower-status.json",
    )
    blocked_effects = read_model["operator_controls"]["blocked_effects"]
    validation = validate_operator_local_developer_workflow_receipt_read_model(read_model=read_model)

    assert validation.ok is True
    assert read_model["status"] == "ready_for_external_pr_execution"
    assert read_model["workflow_status"]["capability_summary"]["status"] == "preflight_ready"
    assert read_model["operator_controls"]["approval_required_before_external_pr"] is True
    assert read_model["operator_controls"]["external_effects_allowed"] is False
    assert all(effect in blocked_effects for effect in FORBIDDEN_EFFECTS)


def test_local_developer_workflow_receipt_validator_rejects_overclaim_and_cycle() -> None:
    read_model = build_operator_local_developer_workflow_receipt_read_model(
        operator_receipt=_operator_receipt(
            readiness_status="awaiting_external_pr_approval",
            external_approved=False,
        ),
        operator_receipt_source_ref="operator-receipt.json",
        control_tower_status_receipt=build_default_operator_control_tower_status_receipt(),
        control_tower_source_ref="control-tower-status.json",
    )
    read_model["operator_controls"]["blocked_effects"].remove("deploy")
    read_model["stage_plan"][1]["predecessors"] = ["approval_handoff"]
    read_model["receipt_card"]["execution_performed"] = True

    validation = validate_operator_local_developer_workflow_receipt_read_model(read_model=read_model)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "blocked_effect_missing:deploy" in serialized_errors
    assert "stage_plan[safe_local_action_selected].dangling_or_cyclic_predecessor:approval_handoff" in serialized_errors
    assert "receipt_card_execution_performed_must_be_false" in serialized_errors


def test_local_developer_workflow_receipt_cli_writes_json(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "local-workflow-receipt-card.json"

    exit_code = main(["--output", str(output_path), "--json"])
    captured = capsys.readouterr()
    read_model = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert read_model["read_model_id"] == "operator_local_developer_workflow_receipt.read_model"
    assert read_model["safe_local_action"]["candidate_id"] == "safe_zone.write_docs"
    assert read_model["operator_controls"]["external_effects_allowed"] is False
    assert '"Local Developer Workflow Receipt"' in captured.out


def test_local_developer_workflow_receipt_cli_rejects_invalid_operator_receipt(tmp_path: Path, capsys) -> None:
    receipt_path = tmp_path / "bad-operator-receipt.json"
    receipt_path.write_text('{"execution_performed": true}\n', encoding="utf-8")
    output_path = tmp_path / "local-workflow-receipt-card.json"

    exit_code = main(["--operator-receipt", str(receipt_path), "--output", str(output_path), "--json"])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert not output_path.exists()
    assert "OPERATOR LOCAL DEVELOPER WORKFLOW RECEIPT INVALID" in captured.out

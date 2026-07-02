"""Tests for the unified operator workflow dashboard projection.

Purpose: prove local workflow status, receipt, safe action, rollback, and
approval fields are visible in one no-effect operator dashboard.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.operator_workflow_dashboard.
Invariants: dashboard rows are projection-only, schema-backed, and block
external repository and connector effects.
"""

from __future__ import annotations

import json
from pathlib import Path

from gateway.operator_workflow_dashboard import (
    FORBIDDEN_EFFECTS,
    build_operator_workflow_dashboard_read_model,
    main,
    validate_operator_workflow_dashboard_read_model,
)
from scripts.build_developer_workflow_operator_receipt import canonical_hash
from scripts.build_operator_local_developer_workflow_receipt_read_model import (
    build_operator_local_developer_workflow_receipt_read_model,
)
from scripts.validate_operator_control_tower_status_receipt import build_default_operator_control_tower_status_receipt


def _operator_receipt(*, readiness_status: str, external_approved: bool) -> dict[str, object]:
    external_ready = readiness_status == "ready_for_external_pr_execution"
    next_evidence = [] if external_ready else ["external_approval_witness", "command_preview"]
    receipt: dict[str, object] = {
        "receipt_id": "developer_workflow_operator_receipt.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": "developer_workflow_v1_dashboard_test",
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


def _local_receipt(*, readiness_status: str = "awaiting_external_pr_approval") -> dict[str, object]:
    return build_operator_local_developer_workflow_receipt_read_model(
        operator_receipt=_operator_receipt(
            readiness_status=readiness_status,
            external_approved=readiness_status == "ready_for_external_pr_execution",
        ),
        operator_receipt_source_ref="operator-receipt.json",
        control_tower_status_receipt=build_default_operator_control_tower_status_receipt(),
        control_tower_source_ref="control-tower-status.json",
    )


def test_operator_workflow_dashboard_exposes_requested_columns() -> None:
    dashboard = build_operator_workflow_dashboard_read_model(
        local_workflow_receipt=_local_receipt(),
        local_workflow_source_ref="local-workflow-receipt.json",
    )
    validation = validate_operator_workflow_dashboard_read_model(dashboard=dashboard)
    row = dashboard["rows"][0]

    assert validation.ok is True
    assert dashboard["read_model_id"] == "operator_workflow_dashboard.read_model"
    assert dashboard["projection_only"] is True
    assert dashboard["execution_performed"] is False
    assert dashboard["external_effects_allowed"] is False
    assert row["task"] == "Mullu Developer Workflow v1"
    assert row["status"] == "awaiting_external_pr_approval"
    assert row["current_gate"]["stage_id"] == "test_gate"
    assert row["missing_evidence"]
    assert row["next_action"] == "approve or defer external PR execution"
    assert row["risk"] == "external repository write"
    assert row["receipts"]["completed"] == 4
    assert row["rollback"]["required"] is True
    assert row["approval_needed"] is True
    assert dashboard["promotion_filters"]["ladder_id"] == "mullu.capability_promotion_ladder.v1"
    assert dashboard["promotion_filters"]["filter_is_not_execution_authority"] is True
    assert dashboard["promotion_filters"]["live_execution_enabled"] is False
    assert [level["level_id"] for level in dashboard["promotion_filters"]["levels"]] == [
        "L0",
        "L1",
        "L2",
        "L3",
        "L4",
        "L5",
        "L6",
        "L7",
        "L8",
        "L9",
    ]
    assert sum(dashboard["promotion_filters"]["level_counts"].values()) == dashboard["promotion_filters"]["capability_count"]


def test_operator_workflow_dashboard_forbids_effect_authority() -> None:
    dashboard = build_operator_workflow_dashboard_read_model(
        local_workflow_receipt=_local_receipt(readiness_status="ready_for_external_pr_execution"),
        local_workflow_source_ref="local-workflow-receipt.json",
    )
    row = dashboard["rows"][0]

    assert all(effect in dashboard["blocked_effects"] for effect in FORBIDDEN_EFFECTS)
    assert row["receipts"]["execution_performed"] is False
    assert row["rollback"]["executed"] is False
    assert row["approval"]["performed"] is False
    assert row["current_gate"]["execution_performed"] is False
    assert row["approval"]["external_effects_allowed"] is False
    assert dashboard["promotion_filters"]["external_effects_allowed"] is False
    assert all(
        level["filter_is_not_execution_authority"] is True
        for level in dashboard["promotion_filters"]["levels"]
    )


def test_operator_workflow_dashboard_validator_rejects_overclaim_and_hash_drift() -> None:
    dashboard = build_operator_workflow_dashboard_read_model(
        local_workflow_receipt=_local_receipt(),
        local_workflow_source_ref="local-workflow-receipt.json",
    )
    dashboard["rows"][0]["approval"]["performed"] = True
    dashboard["blocked_effects"].remove("deploy")
    dashboard["promotion_filters"]["live_execution_enabled"] = True
    dashboard["promotion_filters"]["levels"][0]["filter_is_not_execution_authority"] = False

    validation = validate_operator_workflow_dashboard_read_model(dashboard=dashboard)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "rows[0].approval_performed_must_be_false" in serialized_errors
    assert "blocked_effect_missing:deploy" in serialized_errors
    assert "promotion_filters_live_execution_must_be_false" in serialized_errors
    assert "promotion_filter[L0].must_not_be_execution_authority" in serialized_errors
    assert "dashboard_hash_mismatch" in serialized_errors


def test_operator_workflow_dashboard_cli_writes_json(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "operator-workflow-dashboard.json"

    exit_code = main(["--output", str(output_path), "--json"])
    captured = capsys.readouterr()
    dashboard = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert dashboard["read_model_id"] == "operator_workflow_dashboard.read_model"
    assert dashboard["rows"][0]["task"] == "Mullu Developer Workflow v1"
    assert dashboard["external_effects_allowed"] is False
    assert dashboard["promotion_filters"]["levels"][8]["level_name"] == "live-connector-read"
    assert '"operator_workflow_dashboard.read_model"' in captured.out


def test_operator_workflow_dashboard_cli_rejects_invalid_local_receipt(tmp_path: Path, capsys) -> None:
    receipt_path = tmp_path / "bad-local-workflow-receipt.json"
    receipt_path.write_text('{"projection_only": false}\n', encoding="utf-8")
    output_path = tmp_path / "operator-workflow-dashboard.json"

    exit_code = main([
        "--local-workflow-receipt",
        str(receipt_path),
        "--output",
        str(output_path),
        "--json",
    ])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert not output_path.exists()
    assert "OPERATOR WORKFLOW DASHBOARD INVALID" in captured.out

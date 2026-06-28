"""Tests for local PR candidate packet building.

Purpose: prove an approved PR-preparation packet can produce a local candidate
packet without opening an external PR.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.build_local_pr_candidate_packet.
Invariants: external effects, branch push, and PR creation remain false.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_local_pr_candidate_packet import (
    build_local_pr_candidate_packet,
    main,
    validate_local_pr_candidate_packet,
)


def _approval_packet(*, approved: bool, complete: bool) -> dict[str, object]:
    return {
        "packet_id": "pr_preparation_approval_packet.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": "developer_workflow_v1_candidate_test",
        "packet_status": "awaiting_operator_approval" if complete and not approved else "approval_recorded",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "pr_creation_allowed": False,
        "approval_required": True,
        "approval_status": "approved" if approved else "pending",
        "next_action": "approve local PR candidate packet preparation",
        "bundle": {
            "bundle_id": "developer_workflow_sandbox_receipt_bundle.v1",
            "bundle_status": "receipts_complete" if complete else "awaiting_receipts",
            "ready": complete,
            "completed_count": 4 if complete else 0,
            "required_count": 4,
            "receipt_ids": [
                "sandbox_patch_receipt",
                "test_gate_receipt",
                "diff_review_receipt",
                "terminal_receipt",
            ],
        },
        "decision_request": {
            "decision_id": "approve_pr_preparation",
            "prompt": "Approve local preparation",
            "allowed_decisions": ["approve_prepare_pr_candidate", "reject", "defer"],
            "default_decision": "defer",
        },
        "authorized_effect_after_approval": "prepare_local_pr_candidate_packet",
        "forbidden_effects": ["open_external_pr", "push_branch", "merge", "deploy", "call_connector"],
        "source_refs": {
            "bundle_path": "bundle.json",
            "bundle_schema": "schemas/developer_workflow_sandbox_receipt_bundle.schema.json",
            "bundle_validator": "python scripts/validate_developer_workflow_sandbox_receipt_bundle.py",
            "packet_builder": "python scripts/build_pr_preparation_approval_packet.py",
        },
        "packet_hash": "not-used-by-candidate-builder",
    }


def test_local_pr_candidate_waits_for_receipts(tmp_path: Path) -> None:
    packet = build_local_pr_candidate_packet(
        approval_packet=_approval_packet(approved=False, complete=False),
        approval_packet_path=tmp_path / "approval.json",
        title="Local candidate",
        branch_name="codex/local-candidate",
        summary="Local candidate summary",
    )
    validation = validate_local_pr_candidate_packet(packet=packet)

    assert validation.ok is True
    assert packet["candidate_status"] == "awaiting_receipts"
    assert packet["candidate_ready"] is False
    assert packet["external_effects_allowed"] is False
    assert packet["pr_creation_allowed"] is False
    assert packet["branch_push_allowed"] is False


def test_local_pr_candidate_waits_for_operator_approval(tmp_path: Path) -> None:
    packet = build_local_pr_candidate_packet(
        approval_packet=_approval_packet(approved=False, complete=True),
        approval_packet_path=tmp_path / "approval.json",
        title="Local candidate",
        branch_name="codex/local-candidate",
        summary="Local candidate summary",
    )

    assert packet["candidate_status"] == "awaiting_operator_approval"
    assert packet["candidate_ready"] is False
    assert packet["bundle"]["ready"] is True


def test_local_pr_candidate_ready_after_approval_and_complete_receipts(tmp_path: Path) -> None:
    packet = build_local_pr_candidate_packet(
        approval_packet=_approval_packet(approved=True, complete=True),
        approval_packet_path=tmp_path / "approval.json",
        title="Local candidate",
        branch_name="codex/local-candidate",
        summary="Local candidate summary",
    )
    validation = validate_local_pr_candidate_packet(packet=packet)

    assert validation.ok is True
    assert packet["candidate_status"] == "ready_for_pr_tool"
    assert packet["candidate_ready"] is True
    assert packet["diff_refs"] == ["sandbox_patch_receipt", "diff_review_receipt"]
    assert packet["test_refs"] == ["test_gate_receipt"]
    assert "open_external_pr" in packet["forbidden_effects"]


def test_local_pr_candidate_rejects_external_authority(tmp_path: Path) -> None:
    packet = build_local_pr_candidate_packet(
        approval_packet=_approval_packet(approved=True, complete=True),
        approval_packet_path=tmp_path / "approval.json",
        title="Local candidate",
        branch_name="codex/local-candidate",
        summary="Local candidate summary",
    )
    packet["pr_creation_allowed"] = True
    packet["branch_push_allowed"] = True
    packet["forbidden_effects"] = ["merge", "deploy", "call_connector"]

    validation = validate_local_pr_candidate_packet(packet=packet)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "$.pr_creation_allowed: expected const False" in serialized_errors
    assert "$.branch_push_allowed: expected const False" in serialized_errors
    assert "missing_forbidden_effect:open_external_pr" in serialized_errors
    assert "packet_hash_mismatch" in serialized_errors


def test_local_pr_candidate_cli_writes_json(tmp_path: Path, capsys) -> None:
    approval_path = tmp_path / "approval.json"
    output_path = tmp_path / "candidate.json"
    approval_path.write_text(json.dumps(_approval_packet(approved=True, complete=True), indent=2) + "\n", encoding="utf-8")

    exit_code = main([
        "--approval-packet",
        str(approval_path),
        "--output",
        str(output_path),
        "--title",
        "Local candidate",
        "--branch-name",
        "codex/local-candidate",
        "--summary",
        "Local candidate summary",
        "--json",
    ])
    captured = capsys.readouterr()
    packet = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert packet["candidate_ready"] is True
    assert packet["candidate_status"] == "ready_for_pr_tool"
    assert '"local_pr_candidate_packet.v1"' in captured.out

"""Tests for external PR execution approval witness building.

Purpose: prove external PR execution approval is explicit and non-executing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.build_external_pr_execution_approval_witness.
Invariants: external effects require local admission plus approved status.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_external_pr_execution_approval_witness import (
    build_external_pr_execution_approval_witness,
    main,
    validate_external_pr_execution_approval_witness,
)


def _admission_packet(*, admitted: bool) -> dict[str, object]:
    return {
        "packet_id": "pr_tool_admission_packet.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": "developer_workflow_v1_external_pr_test",
        "admission_status": "local_tool_admitted" if admitted else "blocked_candidate_incomplete",
        "local_pr_tool_admitted": admitted,
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "pr_creation_allowed": False,
        "branch_push_allowed": False,
        "candidate": {
            "candidate_status": "ready_for_pr_tool" if admitted else "awaiting_receipts",
            "candidate_ready": admitted,
            "candidate_packet_hash": "b" * 64,
            "title": "Local candidate",
            "branch_name": "codex/local-candidate",
            "diff_refs": ["sandbox_patch_receipt", "diff_review_receipt"] if admitted else [],
            "test_refs": ["test_gate_receipt"] if admitted else [],
            "rollback_evidence_refs": ["sandbox_patch_receipt"] if admitted else [],
        },
        "local_tool_actions_allowed": [
            "render_pr_body",
            "assemble_pr_metadata",
            "prepare_pr_command_preview",
        ] if admitted else [],
        "external_approval_required_before_execution": True,
        "forbidden_effects": ["open_external_pr", "push_branch", "merge", "deploy", "call_connector"],
        "source_refs": {
            "candidate_packet_path": "candidate.json",
            "candidate_packet_schema": "schemas/local_pr_candidate_packet.schema.json",
            "admission_builder": "python scripts/build_pr_tool_admission_packet.py",
        },
        "packet_hash": "a" * 64,
    }


def test_external_pr_witness_waits_for_local_admission(tmp_path: Path) -> None:
    witness = build_external_pr_execution_approval_witness(
        admission_packet=_admission_packet(admitted=False),
        admission_packet_path=tmp_path / "admission.json",
        approval_status="approved",
    )
    validation = validate_external_pr_execution_approval_witness(witness=witness)

    assert validation.ok is True
    assert witness["execution_status"] == "awaiting_local_pr_tool_admission"
    assert witness["external_effects_allowed"] is False
    assert witness["pr_creation_allowed"] is False
    assert witness["branch_push_allowed"] is False
    assert witness["approved_external_effects"] == []


def test_external_pr_witness_waits_for_operator_approval(tmp_path: Path) -> None:
    witness = build_external_pr_execution_approval_witness(
        admission_packet=_admission_packet(admitted=True),
        admission_packet_path=tmp_path / "admission.json",
        approval_status="pending",
    )

    assert witness["execution_status"] == "awaiting_operator_approval"
    assert witness["operator_approved_external_effects"] is False
    assert witness["external_effects_allowed"] is False


def test_external_pr_witness_approves_only_after_local_admission_and_approval(tmp_path: Path) -> None:
    witness = build_external_pr_execution_approval_witness(
        admission_packet=_admission_packet(admitted=True),
        admission_packet_path=tmp_path / "admission.json",
        approval_status="approved",
    )
    validation = validate_external_pr_execution_approval_witness(witness=witness)

    assert validation.ok is True
    assert witness["execution_status"] == "approved_for_external_pr_execution"
    assert witness["external_effects_allowed"] is True
    assert witness["pr_creation_allowed"] is True
    assert witness["branch_push_allowed"] is True
    assert witness["approved_external_effects"] == ["push_branch", "open_external_pr"]


def test_external_pr_witness_rejects_inconsistent_overclaim(tmp_path: Path) -> None:
    witness = build_external_pr_execution_approval_witness(
        admission_packet=_admission_packet(admitted=False),
        admission_packet_path=tmp_path / "admission.json",
        approval_status="pending",
    )
    witness["external_effects_allowed"] = True
    witness["pr_creation_allowed"] = True
    witness["branch_push_allowed"] = True
    witness["approved_external_effects"] = ["push_branch", "open_external_pr"]

    validation = validate_external_pr_execution_approval_witness(witness=witness)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "external_effects_allowed_mismatch" in serialized_errors
    assert "pr_creation_allowed_mismatch" in serialized_errors
    assert "branch_push_allowed_mismatch" in serialized_errors
    assert "approved_external_effects_mismatch" in serialized_errors
    assert "witness_hash_mismatch" in serialized_errors


def test_external_pr_witness_cli_writes_json(tmp_path: Path, capsys) -> None:
    admission_path = tmp_path / "admission.json"
    output_path = tmp_path / "witness.json"
    admission_path.write_text(json.dumps(_admission_packet(admitted=True), indent=2) + "\n", encoding="utf-8")

    exit_code = main([
        "--admission-packet",
        str(admission_path),
        "--output",
        str(output_path),
        "--approval-status",
        "approved",
        "--json",
    ])
    captured = capsys.readouterr()
    witness = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert witness["execution_status"] == "approved_for_external_pr_execution"
    assert witness["external_effects_allowed"] is True
    assert '"external_pr_execution_approval_witness.v1"' in captured.out

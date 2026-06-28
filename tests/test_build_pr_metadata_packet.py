"""Tests for PR metadata packet building.

Purpose: prove PR title/body metadata is preview-only and candidate-bound.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.build_pr_metadata_packet.
Invariants: PR metadata never grants branch push or PR creation authority.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_pr_metadata_packet import build_pr_metadata_packet, main, validate_pr_metadata_packet


def _candidate_packet(*, ready: bool) -> dict[str, object]:
    return {
        "packet_id": "local_pr_candidate_packet.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": "developer_workflow_v1_metadata_test",
        "candidate_status": "ready_for_pr_tool" if ready else "awaiting_receipts",
        "candidate_ready": ready,
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "pr_creation_allowed": False,
        "branch_push_allowed": False,
        "title": "Local metadata candidate",
        "branch_name": "codex/local-metadata-candidate",
        "summary": "Local metadata candidate summary.",
        "approval": {
            "approval_status": "approved" if ready else "pending",
            "approval_required": True,
            "authorized_effect": "prepare_local_pr_candidate_packet",
        },
        "bundle": {
            "ready": ready,
            "completed_count": 4 if ready else 0,
            "required_count": 4,
            "receipt_ids": ["sandbox_patch_receipt", "test_gate_receipt", "diff_review_receipt", "terminal_receipt"],
        },
        "diff_refs": ["sandbox_patch_receipt", "diff_review_receipt"] if ready else [],
        "test_refs": ["test_gate_receipt"] if ready else [],
        "rollback": {
            "required": True,
            "command": "use sandbox receipt rollback_command",
            "evidence_refs": ["sandbox_patch_receipt"] if ready else [],
        },
        "forbidden_effects": ["open_external_pr", "push_branch", "merge", "deploy", "call_connector"],
        "source_refs": {
            "approval_packet_path": "approval.json",
            "approval_packet_schema": "schemas/pr_preparation_approval_packet.schema.json",
            "candidate_builder": "python scripts/build_local_pr_candidate_packet.py",
        },
        "packet_hash": "a" * 64,
    }


def _preview_packet(*, rendered: bool) -> dict[str, object]:
    return {
        "packet_id": "pr_command_preview_packet.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": "developer_workflow_v1_metadata_test",
        "preview_status": "commands_rendered" if rendered else "blocked",
        "preview_only": True,
        "execution_performed": False,
        "external_effects_allowed_by_witness": rendered,
        "commands_rendered": rendered,
        "blocked_reason": "" if rendered else "local_pr_tool_admission_missing",
        "witness": {
            "approval_status": "approved" if rendered else "pending",
            "execution_status": "approved_for_external_pr_execution" if rendered else "awaiting_local_pr_tool_admission",
            "witness_hash": "b" * 64,
            "branch_name": "codex/local-metadata-candidate",
            "candidate_title": "Local metadata candidate",
        },
        "command_preview": [],
        "rollback_preview": [
            {"rollback_id": "delete_remote_branch", "command": "git push origin --delete codex/local-metadata-candidate"},
            {"rollback_id": "close_external_pr", "command": "gh pr close <pr-number>"},
        ],
        "source_refs": {
            "approval_witness_path": "witness.json",
            "approval_witness_schema": "schemas/external_pr_execution_approval_witness.schema.json",
            "preview_builder": "python scripts/build_pr_command_preview_packet.py",
        },
        "packet_hash": "c" * 64,
    }


def test_pr_metadata_packet_blocks_incomplete_candidate(tmp_path: Path) -> None:
    packet = build_pr_metadata_packet(
        candidate_packet=_candidate_packet(ready=False),
        candidate_packet_path=tmp_path / "candidate.json",
        command_preview_packet=_preview_packet(rendered=False),
        command_preview_packet_path=tmp_path / "preview.json",
    )
    validation = validate_pr_metadata_packet(packet=packet)

    assert validation.ok is True
    assert packet["metadata_status"] == "blocked_candidate_incomplete"
    assert packet["preview_only"] is True
    assert packet["execution_performed"] is False
    assert packet["pr_creation_allowed"] is False


def test_pr_metadata_packet_ready_for_preview_with_candidate(tmp_path: Path) -> None:
    packet = build_pr_metadata_packet(
        candidate_packet=_candidate_packet(ready=True),
        candidate_packet_path=tmp_path / "candidate.json",
        command_preview_packet=_preview_packet(rendered=True),
        command_preview_packet_path=tmp_path / "preview.json",
    )
    validation = validate_pr_metadata_packet(packet=packet)

    assert validation.ok is True
    assert packet["metadata_status"] == "ready_for_preview"
    assert packet["title"] == "Local metadata candidate"
    assert packet["source_branch"] == "codex/local-metadata-candidate"
    assert packet["command_preview"]["preview_status"] == "commands_rendered"
    assert "test_gate_receipt" in packet["body"]["testing"][-2]


def test_pr_metadata_packet_rejects_authority_overclaim(tmp_path: Path) -> None:
    packet = build_pr_metadata_packet(
        candidate_packet=_candidate_packet(ready=True),
        candidate_packet_path=tmp_path / "candidate.json",
    )
    packet["pr_creation_allowed"] = True
    packet["branch_push_allowed"] = True

    validation = validate_pr_metadata_packet(packet=packet)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "$.pr_creation_allowed: expected const False" in serialized_errors
    assert "$.branch_push_allowed: expected const False" in serialized_errors
    assert "pr_creation_allowed_must_be_false" in serialized_errors
    assert "branch_push_allowed_must_be_false" in serialized_errors
    assert "packet_hash_mismatch" in serialized_errors


def test_pr_metadata_packet_cli_writes_json(tmp_path: Path, capsys) -> None:
    candidate_path = tmp_path / "candidate.json"
    preview_path = tmp_path / "preview.json"
    output_path = tmp_path / "metadata.json"
    candidate_path.write_text(json.dumps(_candidate_packet(ready=True), indent=2) + "\n", encoding="utf-8")
    preview_path.write_text(json.dumps(_preview_packet(rendered=True), indent=2) + "\n", encoding="utf-8")

    exit_code = main([
        "--candidate-packet",
        str(candidate_path),
        "--command-preview-packet",
        str(preview_path),
        "--output",
        str(output_path),
        "--json",
    ])
    captured = capsys.readouterr()
    packet = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert packet["metadata_status"] == "ready_for_preview"
    assert packet["title"] == "Local metadata candidate"
    assert '"pr_metadata_packet.v1"' in captured.out

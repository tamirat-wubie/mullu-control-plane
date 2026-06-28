"""Tests for PR tool admission packet building.

Purpose: prove local PR candidate readiness admits only local PR-tool prep.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.build_pr_tool_admission_packet.
Invariants: external effects, branch push, and PR creation remain false.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_pr_tool_admission_packet import (
    build_pr_tool_admission_packet,
    main,
    validate_pr_tool_admission_packet,
)


def _candidate_packet(*, ready: bool) -> dict[str, object]:
    return {
        "packet_id": "local_pr_candidate_packet.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": "developer_workflow_v1_pr_tool_test",
        "candidate_status": "ready_for_pr_tool" if ready else "awaiting_receipts",
        "candidate_ready": ready,
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "pr_creation_allowed": False,
        "branch_push_allowed": False,
        "title": "Local candidate",
        "branch_name": "codex/local-candidate",
        "summary": "Local candidate summary",
        "approval": {
            "approval_status": "approved" if ready else "pending",
            "approval_required": True,
            "authorized_effect": "prepare_local_pr_candidate_packet",
        },
        "bundle": {
            "ready": ready,
            "completed_count": 4 if ready else 0,
            "required_count": 4,
            "receipt_ids": [
                "sandbox_patch_receipt",
                "test_gate_receipt",
                "diff_review_receipt",
                "terminal_receipt",
            ],
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


def test_pr_tool_admission_blocks_incomplete_candidate(tmp_path: Path) -> None:
    packet = build_pr_tool_admission_packet(
        candidate_packet=_candidate_packet(ready=False),
        candidate_packet_path=tmp_path / "candidate.json",
    )
    validation = validate_pr_tool_admission_packet(packet=packet)

    assert validation.ok is True
    assert packet["admission_status"] == "blocked_candidate_incomplete"
    assert packet["local_pr_tool_admitted"] is False
    assert packet["local_tool_actions_allowed"] == []
    assert packet["pr_creation_allowed"] is False
    assert packet["branch_push_allowed"] is False


def test_pr_tool_admission_allows_only_local_actions_for_ready_candidate(tmp_path: Path) -> None:
    packet = build_pr_tool_admission_packet(
        candidate_packet=_candidate_packet(ready=True),
        candidate_packet_path=tmp_path / "candidate.json",
    )
    validation = validate_pr_tool_admission_packet(packet=packet)

    assert validation.ok is True
    assert packet["admission_status"] == "local_tool_admitted"
    assert packet["local_pr_tool_admitted"] is True
    assert packet["local_tool_actions_allowed"] == [
        "render_pr_body",
        "assemble_pr_metadata",
        "prepare_pr_command_preview",
    ]
    assert packet["external_approval_required_before_execution"] is True
    assert "open_external_pr" in packet["forbidden_effects"]


def test_pr_tool_admission_rejects_external_overclaim(tmp_path: Path) -> None:
    packet = build_pr_tool_admission_packet(
        candidate_packet=_candidate_packet(ready=True),
        candidate_packet_path=tmp_path / "candidate.json",
    )
    packet["external_effects_allowed"] = True
    packet["pr_creation_allowed"] = True
    packet["branch_push_allowed"] = True
    packet["forbidden_effects"] = ["merge", "deploy", "call_connector"]

    validation = validate_pr_tool_admission_packet(packet=packet)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "$.external_effects_allowed: expected const False" in serialized_errors
    assert "$.pr_creation_allowed: expected const False" in serialized_errors
    assert "$.branch_push_allowed: expected const False" in serialized_errors
    assert "missing_forbidden_effect:open_external_pr" in serialized_errors
    assert "packet_hash_mismatch" in serialized_errors


def test_pr_tool_admission_cli_writes_json(tmp_path: Path, capsys) -> None:
    candidate_path = tmp_path / "candidate.json"
    output_path = tmp_path / "admission.json"
    candidate_path.write_text(json.dumps(_candidate_packet(ready=True), indent=2) + "\n", encoding="utf-8")

    exit_code = main([
        "--candidate-packet",
        str(candidate_path),
        "--output",
        str(output_path),
        "--json",
    ])
    captured = capsys.readouterr()
    packet = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert packet["local_pr_tool_admitted"] is True
    assert packet["admission_status"] == "local_tool_admitted"
    assert '"pr_tool_admission_packet.v1"' in captured.out

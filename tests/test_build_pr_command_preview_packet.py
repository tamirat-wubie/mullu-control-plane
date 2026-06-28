"""Tests for PR command preview packet building.

Purpose: prove PR command text is non-executing and authority-bound.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.build_pr_command_preview_packet.
Invariants: blocked previews render no push or PR creation command text.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_pr_command_preview_packet import (
    build_pr_command_preview_packet,
    main,
    validate_pr_command_preview_packet,
)


def _approval_witness(*, approved: bool, local_admitted: bool = True) -> dict[str, object]:
    authority_ready = approved and local_admitted
    return {
        "witness_id": "external_pr_execution_approval_witness.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": "developer_workflow_v1_preview_test",
        "approval_status": "approved" if approved else "pending",
        "execution_status": (
            "approved_for_external_pr_execution"
            if authority_ready
            else "awaiting_operator_approval"
            if local_admitted
            else "awaiting_local_pr_tool_admission"
        ),
        "execution_boundary": "external_repository_pr",
        "operator_approved_external_effects": authority_ready,
        "external_effects_allowed": authority_ready,
        "pr_creation_allowed": authority_ready,
        "branch_push_allowed": authority_ready,
        "approved_external_effects": ["push_branch", "open_external_pr"] if authority_ready else [],
        "admission": {
            "admission_status": "local_tool_admitted" if local_admitted else "blocked_candidate_incomplete",
            "local_pr_tool_admitted": local_admitted,
            "admission_packet_hash": "a" * 64,
            "candidate_title": "Local candidate",
            "branch_name": "codex/local-candidate",
            "local_tool_actions_allowed": [
                "render_pr_body",
                "assemble_pr_metadata",
                "prepare_pr_command_preview",
            ] if local_admitted else [],
        },
        "required_before_execution": [
            "local_pr_tool_admission",
            "operator_external_pr_approval",
            "rollback_plan",
            "diff_and_test_receipts",
            "workspace_boundary",
        ],
        "rollback": {
            "required": True,
            "branch_delete_command": "git push origin --delete <branch>",
            "pr_close_command": "gh pr close <pr-number>",
            "evidence_refs": ["sandbox_patch_receipt"] if local_admitted else [],
        },
        "forbidden_without_approval": ["push_branch", "open_external_pr", "merge", "deploy", "call_connector"],
        "source_refs": {
            "admission_packet_path": "admission.json",
            "admission_packet_schema": "schemas/pr_tool_admission_packet.schema.json",
            "witness_builder": "python scripts/build_external_pr_execution_approval_witness.py",
        },
        "witness_hash": "b" * 64,
    }


def test_pr_command_preview_blocks_without_local_admission(tmp_path: Path) -> None:
    packet = build_pr_command_preview_packet(
        approval_witness=_approval_witness(approved=True, local_admitted=False),
        approval_witness_path=tmp_path / "witness.json",
    )
    validation = validate_pr_command_preview_packet(packet=packet)

    assert validation.ok is True
    assert packet["preview_status"] == "blocked"
    assert packet["commands_rendered"] is False
    assert packet["command_preview"] == []
    assert packet["blocked_reason"] == "local_pr_tool_admission_missing"
    assert packet["execution_performed"] is False


def test_pr_command_preview_blocks_without_operator_approval(tmp_path: Path) -> None:
    packet = build_pr_command_preview_packet(
        approval_witness=_approval_witness(approved=False),
        approval_witness_path=tmp_path / "witness.json",
    )

    assert packet["preview_status"] == "blocked"
    assert packet["commands_rendered"] is False
    assert packet["command_preview"] == []
    assert packet["blocked_reason"] == "operator_external_pr_approval_missing"


def test_pr_command_preview_renders_commands_after_authority(tmp_path: Path) -> None:
    packet = build_pr_command_preview_packet(
        approval_witness=_approval_witness(approved=True),
        approval_witness_path=tmp_path / "witness.json",
        pr_body_path=".change_assurance/body.md",
    )
    validation = validate_pr_command_preview_packet(packet=packet)

    assert validation.ok is True
    assert packet["preview_status"] == "commands_rendered"
    assert packet["commands_rendered"] is True
    assert packet["execution_performed"] is False
    assert [item["effect"] for item in packet["command_preview"]] == ["push_branch", "open_external_pr"]
    assert packet["command_preview"][0]["command"] == "git push -u origin codex/local-candidate"
    assert "gh pr create --title 'Local candidate'" in packet["command_preview"][1]["command"]


def test_pr_command_preview_rejects_blocked_commands(tmp_path: Path) -> None:
    packet = build_pr_command_preview_packet(
        approval_witness=_approval_witness(approved=False),
        approval_witness_path=tmp_path / "witness.json",
    )
    packet["command_preview"] = [
        {"command_id": "push_branch", "effect": "push_branch", "command": "git push -u origin codex/local-candidate"}
    ]

    validation = validate_pr_command_preview_packet(packet=packet)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "blocked_preview_must_not_render_commands" in serialized_errors
    assert "packet_hash_mismatch" in serialized_errors


def test_pr_command_preview_cli_writes_json(tmp_path: Path, capsys) -> None:
    witness_path = tmp_path / "witness.json"
    output_path = tmp_path / "preview.json"
    witness_path.write_text(json.dumps(_approval_witness(approved=True), indent=2) + "\n", encoding="utf-8")

    exit_code = main([
        "--approval-witness",
        str(witness_path),
        "--output",
        str(output_path),
        "--json",
    ])
    captured = capsys.readouterr()
    packet = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert packet["preview_status"] == "commands_rendered"
    assert packet["commands_rendered"] is True
    assert '"pr_command_preview_packet.v1"' in captured.out

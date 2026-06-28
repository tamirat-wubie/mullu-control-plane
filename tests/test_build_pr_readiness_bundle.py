"""Tests for PR readiness bundle building.

Purpose: prove the operator-facing PR readiness bundle links all governed PR
artifacts without executing external effects.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.build_pr_readiness_bundle.
Invariants: readiness is derived from upstream artifact status and hash records.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_pr_readiness_bundle import build_pr_readiness_bundle, main, validate_pr_readiness_bundle


def _sandbox_receipts(*, ready: bool) -> dict[str, object]:
    return {
        "bundle_id": "developer_workflow_sandbox_receipt_bundle.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": "developer_workflow_v1_readiness_test",
        "bundle_status": "receipts_complete" if ready else "awaiting_receipts",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "rollback_default": True,
        "required_count": 4,
        "completed_count": 4 if ready else 0,
        "receipts": [],
    }


def _approval_packet(*, ready: bool) -> dict[str, object]:
    return {"workflow_run_id": "developer_workflow_v1_readiness_test", "approval_status": "approved" if ready else "pending"}


def _local_candidate(*, ready: bool) -> dict[str, object]:
    return {
        "workflow_run_id": "developer_workflow_v1_readiness_test",
        "candidate_status": "ready_for_pr_tool" if ready else "awaiting_receipts",
        "candidate_ready": ready,
        "packet_hash": "a" * 64,
    }


def _pr_tool_admission(*, ready: bool) -> dict[str, object]:
    return {
        "workflow_run_id": "developer_workflow_v1_readiness_test",
        "admission_status": "local_tool_admitted" if ready else "blocked_candidate_incomplete",
        "local_pr_tool_admitted": ready,
        "packet_hash": "b" * 64,
    }


def _external_witness(*, ready: bool) -> dict[str, object]:
    return {
        "workflow_run_id": "developer_workflow_v1_readiness_test",
        "execution_status": "approved_for_external_pr_execution" if ready else "awaiting_local_pr_tool_admission",
        "external_effects_allowed": ready,
        "witness_hash": "c" * 64,
    }


def _command_preview(*, ready: bool) -> dict[str, object]:
    return {
        "workflow_run_id": "developer_workflow_v1_readiness_test",
        "preview_status": "commands_rendered" if ready else "blocked",
        "commands_rendered": ready,
        "packet_hash": "d" * 64,
        "rollback_preview": [
            {"rollback_id": "delete_remote_branch", "command": "git push origin --delete codex/readiness"},
            {"rollback_id": "close_external_pr", "command": "gh pr close <pr-number>"},
        ],
    }


def _metadata(*, ready: bool) -> dict[str, object]:
    return {
        "workflow_run_id": "developer_workflow_v1_readiness_test",
        "metadata_status": "ready_for_preview" if ready else "blocked_candidate_incomplete",
        "packet_hash": "e" * 64,
        "rollback": {"evidence_refs": ["sandbox_patch_receipt"] if ready else []},
    }


def _build_bundle(*, ready: bool, tmp_path: Path) -> dict[str, object]:
    return build_pr_readiness_bundle(
        sandbox_receipts=_sandbox_receipts(ready=ready),
        sandbox_receipts_path=tmp_path / "receipts.json",
        approval_packet=_approval_packet(ready=ready),
        approval_packet_path=tmp_path / "approval.json",
        local_candidate=_local_candidate(ready=ready),
        local_candidate_path=tmp_path / "candidate.json",
        pr_tool_admission=_pr_tool_admission(ready=ready),
        pr_tool_admission_path=tmp_path / "admission.json",
        external_witness=_external_witness(ready=ready),
        external_witness_path=tmp_path / "witness.json",
        command_preview=_command_preview(ready=ready),
        command_preview_path=tmp_path / "preview.json",
        metadata=_metadata(ready=ready),
        metadata_path=tmp_path / "metadata.json",
    )


def test_pr_readiness_bundle_blocks_on_missing_receipts(tmp_path: Path) -> None:
    bundle = _build_bundle(ready=False, tmp_path=tmp_path)
    validation = validate_pr_readiness_bundle(bundle=bundle)

    assert validation.ok is True
    assert bundle["readiness_status"] == "awaiting_sandbox_receipts"
    assert bundle["ready_for_external_pr_execution"] is False
    assert bundle["external_effects_allowed"] is False
    assert "sandbox_receipts" in bundle["next_evidence"]


def test_pr_readiness_bundle_ready_when_all_artifacts_ready(tmp_path: Path) -> None:
    bundle = _build_bundle(ready=True, tmp_path=tmp_path)
    validation = validate_pr_readiness_bundle(bundle=bundle)

    assert validation.ok is True
    assert bundle["readiness_status"] == "ready_for_external_pr_execution"
    assert bundle["ready_for_external_pr_execution"] is True
    assert bundle["pr_creation_allowed"] is True
    assert bundle["branch_push_allowed"] is True
    assert bundle["next_evidence"] == []


def test_pr_readiness_bundle_rejects_readiness_overclaim(tmp_path: Path) -> None:
    bundle = _build_bundle(ready=False, tmp_path=tmp_path)
    bundle["ready_for_external_pr_execution"] = True
    bundle["external_effects_allowed"] = True
    bundle["pr_creation_allowed"] = True
    bundle["branch_push_allowed"] = True

    validation = validate_pr_readiness_bundle(bundle=bundle)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "ready_for_external_pr_execution_mismatch" in serialized_errors
    assert "external_effects_allowed_mismatch" in serialized_errors
    assert "pr_creation_allowed_mismatch" in serialized_errors
    assert "branch_push_allowed_mismatch" in serialized_errors
    assert "bundle_hash_mismatch" in serialized_errors


def test_pr_readiness_bundle_cli_writes_json(tmp_path: Path, capsys) -> None:
    paths = {
        "sandbox": tmp_path / "receipts.json",
        "approval": tmp_path / "approval.json",
        "candidate": tmp_path / "candidate.json",
        "admission": tmp_path / "admission.json",
        "witness": tmp_path / "witness.json",
        "preview": tmp_path / "preview.json",
        "metadata": tmp_path / "metadata.json",
        "output": tmp_path / "readiness.json",
    }
    payloads = {
        paths["sandbox"]: _sandbox_receipts(ready=True),
        paths["approval"]: _approval_packet(ready=True),
        paths["candidate"]: _local_candidate(ready=True),
        paths["admission"]: _pr_tool_admission(ready=True),
        paths["witness"]: _external_witness(ready=True),
        paths["preview"]: _command_preview(ready=True),
        paths["metadata"]: _metadata(ready=True),
    }
    for path, payload in payloads.items():
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    exit_code = main([
        "--sandbox-receipts", str(paths["sandbox"]),
        "--approval-packet", str(paths["approval"]),
        "--local-candidate", str(paths["candidate"]),
        "--pr-tool-admission", str(paths["admission"]),
        "--external-witness", str(paths["witness"]),
        "--command-preview", str(paths["preview"]),
        "--metadata", str(paths["metadata"]),
        "--output", str(paths["output"]),
        "--json",
    ])
    captured = capsys.readouterr()
    bundle = json.loads(paths["output"].read_text(encoding="utf-8"))

    assert exit_code == 0
    assert bundle["readiness_status"] == "ready_for_external_pr_execution"
    assert bundle["ready_for_external_pr_execution"] is True
    assert '"pr_readiness_bundle.v1"' in captured.out

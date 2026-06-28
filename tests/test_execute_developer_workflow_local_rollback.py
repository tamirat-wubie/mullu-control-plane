"""Tests for Developer Workflow local rollback execution.

Purpose: prove approved local rollback can delete selected generated artifacts
only inside the workspace root and emits a governed receipt.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.execute_developer_workflow_local_rollback.
Invariants: execution requires approval, workspace containment, and receipt
validation; dry-run never deletes.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_developer_workflow_local_rollback_approval_packet import (
    build_developer_workflow_local_rollback_approval_packet,
    write_developer_workflow_local_rollback_approval_packet,
)
from scripts.execute_developer_workflow_local_rollback import (
    build_developer_workflow_local_rollback_execution_receipt,
    main,
    write_developer_workflow_local_rollback_execution_receipt,
)
from scripts.validate_developer_workflow_local_rollback_execution_receipt import (
    validate_developer_workflow_local_rollback_execution_receipt,
)


ROOT = Path(__file__).resolve().parents[1]


def _summary_for_workspace(workspace_root: Path, artifact_path: Path) -> dict[str, object]:
    path_label = artifact_path.relative_to(workspace_root).as_posix()
    return {
        "packet_id": "developer_workflow_local_rollback_summary_packet.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": "developer_workflow_v1_test_rollback",
        "packet_status": "rollback_ready",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "rollback_execution_performed": False,
        "source_report_path": "test-proof-report.json",
        "generated_artifact_count": 1,
        "rollback_command_preview": [f"Remove-Item -LiteralPath '{path_label}' -Force"],
        "source_refs": {
            "local_sandbox_proof_report": "test-proof-report.json",
            "builder": "python scripts/build_developer_workflow_local_rollback_summary_packet.py",
            "validator": "python scripts/validate_developer_workflow_local_rollback_summary_packet.py",
        },
        "artifacts": [
            {
                "artifact_id": "generated_receipt",
                "path": path_label,
                "artifact_status": "reported",
                "rollback_action": "delete_generated_artifact",
                "rollback_command": f"Remove-Item -LiteralPath '{path_label}' -Force",
                "required_confirmation": True,
            }
        ],
    }


def _approved_packet(tmp_path: Path, artifact_path: Path) -> tuple[dict[str, object], Path]:
    workspace_root = artifact_path.parent
    summary = _summary_for_workspace(workspace_root, artifact_path)
    summary_path = tmp_path / "rollback-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    approval = build_developer_workflow_local_rollback_approval_packet(
        local_rollback_summary_packet=summary,
        local_rollback_summary_packet_path=summary_path,
        approval_status="approved",
        selected_artifact_ids=("generated_receipt",),
        approved_by="operator",
        approved_at="2026-05-01T12:00:00+00:00",
        approval_evidence_ref="approval://local/rollback/generated-receipt",
    )
    return approval, summary_path


def test_local_rollback_execution_dry_run_preserves_file(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    artifact_path = workspace_root / "generated.json"
    artifact_path.write_text("generated", encoding="utf-8")
    approval, summary_path = _approved_packet(tmp_path, artifact_path)

    receipt = build_developer_workflow_local_rollback_execution_receipt(
        approval_packet=approval,
        approval_packet_path=tmp_path / "approval.json",
        rollback_summary_path=summary_path,
        workspace_root=workspace_root,
        execute=False,
    )
    receipt_path = write_developer_workflow_local_rollback_execution_receipt(receipt, tmp_path / "receipt.json")
    validation = validate_developer_workflow_local_rollback_execution_receipt(receipt_path=receipt_path)

    assert validation.ok is True
    assert receipt["execution_status"] == "dry_run_ready"
    assert receipt["execution_mode"] == "dry_run"
    assert receipt["rollback_execution_performed"] is False
    assert receipt["executed_artifact_count"] == 0
    assert receipt["artifacts"][0]["action_status"] == "would_delete"  # type: ignore[index]
    assert artifact_path.exists()


def test_local_rollback_execution_deletes_approved_file(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    artifact_path = workspace_root / "generated.json"
    artifact_path.write_text("generated", encoding="utf-8")
    approval, summary_path = _approved_packet(tmp_path, artifact_path)

    receipt = build_developer_workflow_local_rollback_execution_receipt(
        approval_packet=approval,
        approval_packet_path=tmp_path / "approval.json",
        rollback_summary_path=summary_path,
        workspace_root=workspace_root,
        execute=True,
    )
    receipt_path = write_developer_workflow_local_rollback_execution_receipt(receipt, tmp_path / "receipt.json")
    validation = validate_developer_workflow_local_rollback_execution_receipt(receipt_path=receipt_path)

    assert validation.ok is True
    assert receipt["execution_status"] == "rollback_executed"
    assert receipt["rollback_execution_performed"] is True
    assert receipt["executed_artifact_count"] == 1
    assert receipt["failed_artifact_count"] == 0
    assert receipt["artifacts"][0]["action_status"] == "deleted"  # type: ignore[index]
    assert artifact_path.exists() is False


def test_local_rollback_execution_blocks_outside_workspace(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    outside_path = tmp_path / "outside.json"
    outside_path.write_text("outside", encoding="utf-8")
    approval = {
        "workflow_run_id": "developer_workflow_v1_test_rollback",
        "approval_status": "approved",
        "delete_execution_allowed": True,
        "selected_artifact_count": 1,
        "authorized_artifacts": [
            {
                "artifact_id": "outside",
                "path": str(outside_path),
                "rollback_command": f"Remove-Item -LiteralPath '{outside_path}' -Force",
                "approval_status": "approved",
                "execution_allowed": True,
                "required_confirmation": True,
            }
        ],
    }

    receipt = build_developer_workflow_local_rollback_execution_receipt(
        approval_packet=approval,
        approval_packet_path=tmp_path / "approval.json",
        rollback_summary_path=tmp_path / "rollback-summary.json",
        workspace_root=workspace_root,
        execute=True,
    )

    assert receipt["execution_status"] == "rollback_failed"
    assert receipt["failed_artifact_count"] == 1
    assert receipt["artifacts"][0]["action_status"] == "boundary_blocked"  # type: ignore[index]
    assert outside_path.exists()


def test_local_rollback_execution_cli_writes_receipt_and_deletes(tmp_path: Path, capsys) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    artifact_path = workspace_root / "generated.json"
    artifact_path.write_text("generated", encoding="utf-8")
    approval, summary_path = _approved_packet(tmp_path, artifact_path)
    approval_path = write_developer_workflow_local_rollback_approval_packet(approval, tmp_path / "approval.json")
    output_path = tmp_path / "execution-receipt.json"

    exit_code = main([
        "--approval-packet",
        str(approval_path),
        "--rollback-summary",
        str(summary_path),
        "--workspace-root",
        str(workspace_root),
        "--output",
        str(output_path),
        "--execute",
        "--json",
    ])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["execution_status"] == "rollback_executed"
    assert payload["executed_artifact_count"] == 1
    assert output_path.exists()
    assert artifact_path.exists() is False

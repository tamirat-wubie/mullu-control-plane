"""Tests for the Developer Workflow local rollback flow.

Purpose: prove one command can record approval, generate a mandatory dry-run,
and optionally execute approved local rollback deletion.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.run_developer_workflow_local_rollback_flow.
Invariants: flow requires selected artifacts or approve-all and never grants
external effects.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.run_developer_workflow_local_rollback_flow import (
    main,
    run_developer_workflow_local_rollback_flow,
)


def _rollback_summary(workspace_root: Path, artifact_path: Path) -> dict[str, object]:
    path_label = artifact_path.relative_to(workspace_root).as_posix()
    return {
        "packet_id": "developer_workflow_local_rollback_summary_packet.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": "developer_workflow_v1_flow_test",
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


def _write_summary(tmp_path: Path) -> tuple[Path, Path, Path]:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    artifact_path = workspace_root / "generated.json"
    artifact_path.write_text("generated", encoding="utf-8")
    summary_path = tmp_path / "rollback-summary.json"
    summary_path.write_text(
        json.dumps(_rollback_summary(workspace_root, artifact_path), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary_path, workspace_root, artifact_path


def test_rollback_flow_requires_selected_artifact_or_approve_all(tmp_path: Path) -> None:
    summary_path, workspace_root, _artifact_path = _write_summary(tmp_path)

    try:
        run_developer_workflow_local_rollback_flow(
            rollback_summary_path=summary_path,
            approval_output_path=tmp_path / "approval.json",
            dry_run_output_path=tmp_path / "dry-run.json",
            execution_output_path=tmp_path / "execution.json",
            workspace_root=workspace_root,
            artifact_ids=(),
            approve_all=False,
            approved_by="operator",
            approved_at="2026-05-01T12:00:00+00:00",
            approval_evidence_ref="approval://local/flow",
            approval_note="test",
            execute=False,
        )
    except ValueError as exc:
        assert "rollback_flow_requires_artifact_id_or_approve_all" in str(exc)
    else:
        raise AssertionError("flow accepted implicit approval")


def test_rollback_flow_writes_approval_and_dry_run_without_deleting(tmp_path: Path) -> None:
    summary_path, workspace_root, artifact_path = _write_summary(tmp_path)
    approval_output = tmp_path / "approval.json"
    dry_run_output = tmp_path / "dry-run.json"
    execution_output = tmp_path / "execution.json"

    result = run_developer_workflow_local_rollback_flow(
        rollback_summary_path=summary_path,
        approval_output_path=approval_output,
        dry_run_output_path=dry_run_output,
        execution_output_path=execution_output,
        workspace_root=workspace_root,
        artifact_ids=("generated_receipt",),
        approve_all=False,
        approved_by="operator",
        approved_at="2026-05-01T12:00:00+00:00",
        approval_evidence_ref="approval://local/flow",
        approval_note="test",
        execute=False,
    )

    assert result["flow_status"] == "dry_run_ready"
    assert result["dry_run_status"] == "dry_run_ready"
    assert result["rollback_execution_performed"] is False
    assert result["selected_artifact_count"] == 1
    assert approval_output.exists()
    assert dry_run_output.exists()
    assert execution_output.exists() is False
    assert artifact_path.exists()


def test_rollback_flow_executes_after_dry_run_when_requested(tmp_path: Path) -> None:
    summary_path, workspace_root, artifact_path = _write_summary(tmp_path)

    result = run_developer_workflow_local_rollback_flow(
        rollback_summary_path=summary_path,
        approval_output_path=tmp_path / "approval.json",
        dry_run_output_path=tmp_path / "dry-run.json",
        execution_output_path=tmp_path / "execution.json",
        workspace_root=workspace_root,
        artifact_ids=("generated_receipt",),
        approve_all=False,
        approved_by="operator",
        approved_at="2026-05-01T12:00:00+00:00",
        approval_evidence_ref="approval://local/flow",
        approval_note="test",
        execute=True,
    )

    assert result["flow_status"] == "executed"
    assert result["dry_run_status"] == "dry_run_ready"
    assert result["execution_status"] == "rollback_executed"
    assert result["rollback_execution_performed"] is True
    assert result["executed_artifact_count"] == 1
    assert artifact_path.exists() is False


def test_rollback_flow_cli_prints_json(tmp_path: Path, capsys) -> None:
    summary_path, workspace_root, artifact_path = _write_summary(tmp_path)

    exit_code = main([
        "--rollback-summary",
        str(summary_path),
        "--approval-output",
        str(tmp_path / "approval.json"),
        "--dry-run-output",
        str(tmp_path / "dry-run.json"),
        "--execution-output",
        str(tmp_path / "execution.json"),
        "--workspace-root",
        str(workspace_root),
        "--artifact-id",
        "generated_receipt",
        "--approved-at",
        "2026-05-01T12:00:00+00:00",
        "--json",
    ])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["flow_status"] == "dry_run_ready"
    assert payload["execution_status"] == "dry_run_ready"
    assert artifact_path.exists()

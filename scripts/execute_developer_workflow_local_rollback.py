#!/usr/bin/env python3
"""Execute approved Developer Workflow local rollback deletion.

Purpose: consume a validated local rollback approval packet, check workspace
boundaries for each selected generated artifact, optionally delete approved
local files, and emit an execution receipt.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: rollback approval validator and rollback execution receipt
validator.
Invariants:
  - No external effects are allowed.
  - Paths must resolve inside the declared workspace root before deletion.
  - Deletion occurs only with --execute and approved selected artifacts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_developer_workflow_local_rollback_approval_packet import (  # noqa: E402
    validate_developer_workflow_local_rollback_approval_packet,
)
from scripts.validate_developer_workflow_local_rollback_execution_receipt import (  # noqa: E402
    validate_developer_workflow_local_rollback_execution_receipt,
)


DEFAULT_APPROVAL_PACKET = REPO_ROOT / ".change_assurance" / "developer_workflow_local_rollback_approval_packet.generated.json"
DEFAULT_ROLLBACK_SUMMARY = REPO_ROOT / ".change_assurance" / "developer_workflow_local_rollback_summary_packet.generated.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "developer_workflow_local_rollback_execution_receipt.generated.json"


def build_developer_workflow_local_rollback_execution_receipt(
    *,
    approval_packet: Mapping[str, Any],
    approval_packet_path: Path,
    rollback_summary_path: Path,
    workspace_root: Path,
    execute: bool,
) -> dict[str, Any]:
    """Return a rollback execution receipt, deleting files only in execute mode."""

    normalized_workspace = workspace_root.resolve(strict=False)
    approved = approval_packet.get("approval_status") == "approved" and approval_packet.get("delete_execution_allowed") is True
    execution_mode = "execute" if execute else "dry_run"
    artifact_rows: list[dict[str, Any]] = []
    artifacts = approval_packet.get("authorized_artifacts", ())
    if not isinstance(artifacts, list):
        artifacts = []
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            continue
        artifact_rows.append(
            _artifact_execution_row(
                artifact=artifact,
                workspace_root=normalized_workspace,
                approved=approved,
                execute=execute,
            )
        )
    executed_count = sum(1 for row in artifact_rows if row["action_status"] == "deleted")
    failed_count = sum(1 for row in artifact_rows if row["action_status"] in {"boundary_blocked", "failed"})
    skipped_count = len(artifact_rows) - executed_count - failed_count
    execution_status = _execution_status(
        approved=approved,
        execution_mode=execution_mode,
        selected_count=int(approval_packet.get("selected_artifact_count", 0) or 0),
        executed_count=executed_count,
        failed_count=failed_count,
    )
    return {
        "receipt_id": "developer_workflow_local_rollback_execution_receipt.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": str(approval_packet.get("workflow_run_id") or "developer_workflow_v1_foundation_run"),
        "execution_status": execution_status,
        "execution_mode": execution_mode,
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "rollback_execution_performed": executed_count > 0,
        "target_path_checks_performed": True,
        "workspace_root": str(normalized_workspace),
        "approval_packet_path": _path_label(approval_packet_path),
        "rollback_summary_path": _path_label(rollback_summary_path),
        "approval_status": str(approval_packet.get("approval_status") or "pending"),
        "delete_execution_allowed": approval_packet.get("delete_execution_allowed") is True,
        "selected_artifact_count": int(approval_packet.get("selected_artifact_count", 0) or 0),
        "executed_artifact_count": executed_count,
        "skipped_artifact_count": skipped_count,
        "failed_artifact_count": failed_count,
        "source_refs": {
            "approval_packet": _path_label(approval_packet_path),
            "rollback_summary_packet": _path_label(rollback_summary_path),
            "runner": "python scripts/execute_developer_workflow_local_rollback.py",
            "validator": "python scripts/validate_developer_workflow_local_rollback_execution_receipt.py",
        },
        "artifacts": artifact_rows,
    }


def write_developer_workflow_local_rollback_execution_receipt(receipt: Mapping[str, Any], output_path: Path) -> Path:
    """Write a deterministic rollback execution receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _artifact_execution_row(
    *,
    artifact: Mapping[str, Any],
    workspace_root: Path,
    approved: bool,
    execute: bool,
) -> dict[str, Any]:
    artifact_id = str(artifact.get("artifact_id") or "")
    raw_path = str(artifact.get("path") or "")
    target_path = _resolve_target_path(raw_path, workspace_root)
    path_within_workspace = _is_within_workspace(target_path, workspace_root)
    pre_exists = target_path.exists()
    action_status = "skipped"
    error_message = ""
    if not approved or artifact.get("execution_allowed") is not True:
        action_status = "skipped"
    elif not path_within_workspace:
        action_status = "boundary_blocked"
        error_message = "target path is outside workspace root"
    elif target_path == workspace_root:
        action_status = "boundary_blocked"
        error_message = "target path is workspace root"
    elif not pre_exists:
        action_status = "missing_before"
    elif not execute:
        action_status = "would_delete"
    else:
        try:
            if target_path.is_dir():
                action_status = "boundary_blocked"
                error_message = "directory deletion is not allowed by this runner"
            else:
                target_path.unlink()
                action_status = "deleted"
        except OSError as exc:
            action_status = "failed"
            error_message = f"delete_failed:{exc.__class__.__name__}"
    return {
        "artifact_id": artifact_id,
        "path": raw_path,
        "resolved_path": str(target_path),
        "rollback_command": str(artifact.get("rollback_command") or ""),
        "approval_status": str(artifact.get("approval_status") or "pending"),
        "execution_allowed": artifact.get("execution_allowed") is True,
        "required_confirmation": artifact.get("required_confirmation") is True,
        "path_within_workspace": path_within_workspace,
        "pre_exists": pre_exists,
        "post_exists": target_path.exists(),
        "action_status": action_status,
        "error_message": error_message,
    }


def _resolve_target_path(raw_path: str, workspace_root: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path.resolve(strict=False)
    return (workspace_root / path).resolve(strict=False)


def _is_within_workspace(path: Path, workspace_root: Path) -> bool:
    try:
        path.relative_to(workspace_root)
    except ValueError:
        return False
    return True


def _execution_status(
    *,
    approved: bool,
    execution_mode: str,
    selected_count: int,
    executed_count: int,
    failed_count: int,
) -> str:
    if not approved:
        return "blocked_no_approval"
    if execution_mode == "dry_run":
        return "dry_run_ready" if selected_count else "blocked_no_approval"
    if failed_count and executed_count:
        return "rollback_partial"
    if failed_count:
        return "rollback_failed"
    if executed_count:
        return "rollback_executed"
    return "rollback_noop"


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"json_parse_failed:{path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"json_root_must_be_object:{path}")
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse local rollback execution arguments."""

    parser = argparse.ArgumentParser(description="Execute approved Developer Workflow local rollback deletion.")
    parser.add_argument("--approval-packet", default=str(DEFAULT_APPROVAL_PACKET))
    parser.add_argument("--rollback-summary", default=str(DEFAULT_ROLLBACK_SUMMARY))
    parser.add_argument("--workspace-root", default=str(REPO_ROOT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for local rollback execution."""

    args = parse_args(argv)
    try:
        approval_packet_path = Path(args.approval_packet)
        rollback_summary_path = Path(args.rollback_summary)
        approval_validation = validate_developer_workflow_local_rollback_approval_packet(
            packet_path=approval_packet_path,
            rollback_summary_path=rollback_summary_path,
        )
        if not approval_validation.ok:
            print(f"DEVELOPER WORKFLOW LOCAL ROLLBACK EXECUTION BLOCKED errors={list(approval_validation.errors)}")
            return 2
        receipt = build_developer_workflow_local_rollback_execution_receipt(
            approval_packet=_load_json_object(approval_packet_path),
            approval_packet_path=approval_packet_path,
            rollback_summary_path=rollback_summary_path,
            workspace_root=Path(args.workspace_root),
            execute=bool(args.execute),
        )
        output_path = write_developer_workflow_local_rollback_execution_receipt(receipt, Path(args.output))
        receipt_validation = validate_developer_workflow_local_rollback_execution_receipt(receipt_path=output_path)
    except ValueError as exc:
        print(f"DEVELOPER WORKFLOW LOCAL ROLLBACK EXECUTION INVALID error={exc}")
        return 2
    if not receipt_validation.ok:
        print(f"DEVELOPER WORKFLOW LOCAL ROLLBACK EXECUTION INVALID errors={list(receipt_validation.errors)}")
        return 2
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        print(
            "DEVELOPER WORKFLOW LOCAL ROLLBACK EXECUTION RECEIPT "
            f"path={output_path} status={receipt['execution_status']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

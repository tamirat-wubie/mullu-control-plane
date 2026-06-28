#!/usr/bin/env python3
"""Run the Developer Workflow local rollback approval and execution flow.

Purpose: compose rollback approval, mandatory dry-run, and optional execution
receipt generation into one local-lab operator command.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: rollback approval builder, rollback execution runner, and their
validators.
Invariants:
  - The flow never grants external effects.
  - At least one selected artifact or explicit approve-all is required.
  - Dry-run receipt is always generated before optional execution.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_developer_workflow_local_rollback_approval_packet import (  # noqa: E402
    build_developer_workflow_local_rollback_approval_packet,
    write_developer_workflow_local_rollback_approval_packet,
)
from scripts.execute_developer_workflow_local_rollback import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_EXECUTION_OUTPUT,
    build_developer_workflow_local_rollback_execution_receipt,
    write_developer_workflow_local_rollback_execution_receipt,
)
from scripts.validate_developer_workflow_local_rollback_approval_packet import (  # noqa: E402
    validate_developer_workflow_local_rollback_approval_packet,
)
from scripts.validate_developer_workflow_local_rollback_execution_receipt import (  # noqa: E402
    validate_developer_workflow_local_rollback_execution_receipt,
)


DEFAULT_ROLLBACK_SUMMARY = REPO_ROOT / ".change_assurance" / "developer_workflow_local_rollback_summary_packet.generated.json"
DEFAULT_APPROVAL_OUTPUT = REPO_ROOT / ".change_assurance" / "developer_workflow_local_rollback_approval_packet.generated.json"
DEFAULT_DRY_RUN_OUTPUT = REPO_ROOT / ".change_assurance" / "developer_workflow_local_rollback_dry_run_receipt.generated.json"


def run_developer_workflow_local_rollback_flow(
    *,
    rollback_summary_path: Path,
    approval_output_path: Path,
    dry_run_output_path: Path,
    execution_output_path: Path,
    workspace_root: Path,
    artifact_ids: Sequence[str],
    approve_all: bool,
    approved_by: str,
    approved_at: str,
    approval_evidence_ref: str,
    approval_note: str,
    execute: bool,
) -> dict[str, Any]:
    """Build approval and dry-run receipts, then optionally execute rollback."""

    rollback_summary = _load_json_object(rollback_summary_path)
    selected_ids = tuple(str(item) for item in artifact_ids if str(item).strip())
    if not selected_ids and not approve_all:
        raise ValueError("rollback_flow_requires_artifact_id_or_approve_all")
    approval_packet = build_developer_workflow_local_rollback_approval_packet(
        local_rollback_summary_packet=rollback_summary,
        local_rollback_summary_packet_path=rollback_summary_path,
        approval_status="approved",
        selected_artifact_ids=selected_ids,
        approved_by=approved_by,
        approved_at=approved_at or datetime.now(UTC).isoformat(),
        approval_evidence_ref=approval_evidence_ref,
        approval_note=approval_note,
    )
    approval_path = write_developer_workflow_local_rollback_approval_packet(
        approval_packet,
        approval_output_path,
    )
    approval_validation = validate_developer_workflow_local_rollback_approval_packet(
        packet_path=approval_path,
        rollback_summary_path=rollback_summary_path,
    )
    if not approval_validation.ok:
        raise ValueError(f"rollback_approval_invalid:{list(approval_validation.errors)}")
    dry_run_receipt = build_developer_workflow_local_rollback_execution_receipt(
        approval_packet=approval_packet,
        approval_packet_path=approval_path,
        rollback_summary_path=rollback_summary_path,
        workspace_root=workspace_root,
        execute=False,
    )
    dry_run_path = write_developer_workflow_local_rollback_execution_receipt(dry_run_receipt, dry_run_output_path)
    dry_run_validation = validate_developer_workflow_local_rollback_execution_receipt(receipt_path=dry_run_path)
    if not dry_run_validation.ok:
        raise ValueError(f"rollback_dry_run_invalid:{list(dry_run_validation.errors)}")
    execution_receipt: Mapping[str, Any] = dry_run_receipt
    execution_path = dry_run_path
    if execute:
        execution_receipt = build_developer_workflow_local_rollback_execution_receipt(
            approval_packet=approval_packet,
            approval_packet_path=approval_path,
            rollback_summary_path=rollback_summary_path,
            workspace_root=workspace_root,
            execute=True,
        )
        execution_path = write_developer_workflow_local_rollback_execution_receipt(
            execution_receipt,
            execution_output_path,
        )
        execution_validation = validate_developer_workflow_local_rollback_execution_receipt(
            receipt_path=execution_path,
        )
        if not execution_validation.ok:
            raise ValueError(f"rollback_execution_invalid:{list(execution_validation.errors)}")
    return {
        "flow_id": "developer_workflow_local_rollback_flow.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": str(approval_packet.get("workflow_run_id") or "developer_workflow_v1_foundation_run"),
        "flow_status": "executed" if execute else "dry_run_ready",
        "external_effects_allowed": False,
        "approval_packet_path": str(approval_path.resolve(strict=False)),
        "dry_run_receipt_path": str(dry_run_path.resolve(strict=False)),
        "execution_receipt_path": str(execution_path.resolve(strict=False)),
        "approval_status": approval_packet["approval_status"],
        "selected_artifact_count": approval_packet["selected_artifact_count"],
        "dry_run_status": dry_run_receipt["execution_status"],
        "execution_status": str(execution_receipt.get("execution_status") or dry_run_receipt["execution_status"]),
        "rollback_execution_performed": execution_receipt.get("rollback_execution_performed") is True,
        "executed_artifact_count": int(execution_receipt.get("executed_artifact_count", 0) or 0),
        "failed_artifact_count": int(execution_receipt.get("failed_artifact_count", 0) or 0),
    }


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


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse local rollback flow arguments."""

    parser = argparse.ArgumentParser(description="Run Developer Workflow local rollback approval/dry-run/execute flow.")
    parser.add_argument("--rollback-summary", default=str(DEFAULT_ROLLBACK_SUMMARY))
    parser.add_argument("--approval-output", default=str(DEFAULT_APPROVAL_OUTPUT))
    parser.add_argument("--dry-run-output", default=str(DEFAULT_DRY_RUN_OUTPUT))
    parser.add_argument("--execution-output", default=str(DEFAULT_EXECUTION_OUTPUT))
    parser.add_argument("--workspace-root", default=str(REPO_ROOT))
    parser.add_argument("--artifact-id", action="append", default=[])
    parser.add_argument("--approve-all", action="store_true")
    parser.add_argument("--approved-by", default="operator")
    parser.add_argument("--approved-at", default="")
    parser.add_argument("--approval-evidence-ref", default="approval://local/rollback-flow/operator-command")
    parser.add_argument("--approval-note", default="Operator-approved local rollback flow.")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for the local rollback flow."""

    args = parse_args(argv)
    try:
        result = run_developer_workflow_local_rollback_flow(
            rollback_summary_path=Path(args.rollback_summary),
            approval_output_path=Path(args.approval_output),
            dry_run_output_path=Path(args.dry_run_output),
            execution_output_path=Path(args.execution_output),
            workspace_root=Path(args.workspace_root),
            artifact_ids=tuple(str(item) for item in args.artifact_id),
            approve_all=bool(args.approve_all),
            approved_by=str(args.approved_by),
            approved_at=str(args.approved_at),
            approval_evidence_ref=str(args.approval_evidence_ref),
            approval_note=str(args.approval_note),
            execute=bool(args.execute),
        )
    except ValueError as exc:
        print(f"DEVELOPER WORKFLOW LOCAL ROLLBACK FLOW INVALID error={exc}")
        return 2
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            "DEVELOPER WORKFLOW LOCAL ROLLBACK FLOW "
            f"status={result['flow_status']} execution={result['execution_status']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

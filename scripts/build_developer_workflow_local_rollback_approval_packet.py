#!/usr/bin/env python3
"""Build the Developer Workflow local rollback approval packet.

Purpose: record operator approval intent for later rollback deletion of
selected local sandbox generated artifacts without executing rollback.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: rollback summary packet and rollback approval validator.
Invariants:
  - Builder never deletes files or executes rollback commands.
  - Approval rows are derived only from the rollback summary artifact rows.
  - Approved execution requires explicit operator evidence and confirmation.
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


DEFAULT_ROLLBACK_SUMMARY = REPO_ROOT / "examples" / "developer_workflow_local_rollback_summary_packet.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "developer_workflow_local_rollback_approval_packet.generated.json"
APPROVAL_STATUSES = ("pending", "approved", "rejected", "deferred")
PACKET_STATUS_BY_APPROVAL = {
    "pending": "awaiting_operator_approval",
    "approved": "approval_recorded",
    "rejected": "approval_rejected",
    "deferred": "approval_deferred",
}


def build_developer_workflow_local_rollback_approval_packet(
    *,
    local_rollback_summary_packet: Mapping[str, Any],
    local_rollback_summary_packet_path: Path,
    approval_status: str = "pending",
    selected_artifact_ids: Sequence[str] = (),
    approved_by: str = "",
    approved_at: str = "",
    approval_evidence_ref: str = "",
    approval_note: str = "",
) -> dict[str, Any]:
    """Return an approval packet for selected rollback summary artifacts."""

    normalized_status = approval_status if approval_status in APPROVAL_STATUSES else "pending"
    summary_artifacts = _artifact_map(local_rollback_summary_packet)
    selected_ids = _selected_artifact_ids(
        summary_artifacts=summary_artifacts,
        requested_artifact_ids=selected_artifact_ids,
        approval_status=normalized_status,
    )
    execution_allowed = normalized_status == "approved" and bool(selected_ids)
    authorized_artifacts = [
        {
            "artifact_id": artifact_id,
            "path": str(summary_artifacts[artifact_id]["path"]),
            "rollback_command": str(summary_artifacts[artifact_id]["rollback_command"]),
            "approval_status": normalized_status,
            "execution_allowed": execution_allowed,
            "required_confirmation": True,
        }
        for artifact_id in selected_ids
    ]
    return {
        "packet_id": "developer_workflow_local_rollback_approval_packet.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": str(
            local_rollback_summary_packet.get("workflow_run_id") or "developer_workflow_v1_foundation_run"
        ),
        "packet_status": PACKET_STATUS_BY_APPROVAL[normalized_status],
        "approval_status": normalized_status,
        "approval_scope": _approval_scope(selected_ids, summary_artifacts),
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "rollback_execution_performed": False,
        "delete_execution_allowed": execution_allowed,
        "source_rollback_summary_path": _path_label(local_rollback_summary_packet_path),
        "selected_artifact_count": len(selected_ids),
        "selected_artifact_ids": list(selected_ids),
        "operator_approval": {
            "approval_status": normalized_status,
            "approved_by": approved_by,
            "approved_at": approved_at,
            "approval_evidence_ref": approval_evidence_ref,
            "approval_note": approval_note,
        },
        "source_refs": {
            "local_rollback_summary_packet": _path_label(local_rollback_summary_packet_path),
            "builder": "python scripts/build_developer_workflow_local_rollback_approval_packet.py",
            "validator": "python scripts/validate_developer_workflow_local_rollback_approval_packet.py",
        },
        "authorized_artifacts": authorized_artifacts,
    }


def write_developer_workflow_local_rollback_approval_packet(packet: Mapping[str, Any], output_path: Path) -> Path:
    """Write a deterministic rollback approval packet."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _selected_artifact_ids(
    *,
    summary_artifacts: Mapping[str, Mapping[str, Any]],
    requested_artifact_ids: Sequence[str],
    approval_status: str,
) -> tuple[str, ...]:
    requested = tuple(str(item) for item in requested_artifact_ids if str(item).strip())
    if requested:
        return requested
    if approval_status == "approved":
        return tuple(sorted(summary_artifacts))
    return ()


def _artifact_map(packet: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    artifacts = packet.get("artifacts", ())
    if not isinstance(artifacts, list):
        return {}
    mapped: dict[str, Mapping[str, Any]] = {}
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            continue
        artifact_id = str(artifact.get("artifact_id") or "")
        if artifact_id:
            mapped[artifact_id] = artifact
    return dict(sorted(mapped.items()))


def _approval_scope(
    selected_ids: Sequence[str],
    summary_artifacts: Mapping[str, Mapping[str, Any]],
) -> str:
    if not selected_ids:
        return "none"
    if set(selected_ids) == set(summary_artifacts):
        return "all_generated_artifacts"
    return "selected_artifacts"


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
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
    """Parse rollback approval builder arguments."""

    parser = argparse.ArgumentParser(description="Build Developer Workflow local rollback approval packet.")
    parser.add_argument("--rollback-summary", default=str(DEFAULT_ROLLBACK_SUMMARY))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--approval-status", default="pending", choices=APPROVAL_STATUSES)
    parser.add_argument("--artifact-id", action="append", default=[])
    parser.add_argument("--approved-by", default="")
    parser.add_argument("--approved-at", default="")
    parser.add_argument("--approval-evidence-ref", default="")
    parser.add_argument("--approval-note", default="")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for rollback approval packet building."""

    args = parse_args(argv)
    try:
        rollback_summary_path = Path(args.rollback_summary)
        packet = build_developer_workflow_local_rollback_approval_packet(
            local_rollback_summary_packet=_load_json_object(rollback_summary_path),
            local_rollback_summary_packet_path=rollback_summary_path,
            approval_status=str(args.approval_status),
            selected_artifact_ids=tuple(str(item) for item in args.artifact_id),
            approved_by=str(args.approved_by),
            approved_at=str(args.approved_at),
            approval_evidence_ref=str(args.approval_evidence_ref),
            approval_note=str(args.approval_note),
        )
        output_path = write_developer_workflow_local_rollback_approval_packet(packet, Path(args.output))
        validation = validate_developer_workflow_local_rollback_approval_packet(
            packet_path=output_path,
            rollback_summary_path=rollback_summary_path,
        )
    except ValueError as exc:
        print(f"DEVELOPER WORKFLOW LOCAL ROLLBACK APPROVAL PACKET BUILD INVALID error={exc}")
        return 2
    if not validation.ok:
        print(f"DEVELOPER WORKFLOW LOCAL ROLLBACK APPROVAL PACKET BUILD INVALID errors={list(validation.errors)}")
        return 2
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(f"DEVELOPER WORKFLOW LOCAL ROLLBACK APPROVAL PACKET BUILT path={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

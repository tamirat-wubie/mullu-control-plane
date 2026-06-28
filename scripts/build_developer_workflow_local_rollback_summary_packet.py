#!/usr/bin/env python3
"""Build the Developer Workflow local rollback summary packet.

Purpose: project generated local sandbox artifacts into operator-visible
rollback command previews without deleting files or executing commands.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: local sandbox proof report and rollback summary validator.
Invariants:
  - Builder is projection-only and never executes rollback commands.
  - Rollback rows are derived only from the validated local proof report.
  - Every generated artifact receives an explicit confirmation requirement.
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

from scripts.validate_developer_workflow_local_rollback_summary_packet import (  # noqa: E402
    validate_developer_workflow_local_rollback_summary_packet,
)


DEFAULT_PROOF_REPORT = REPO_ROOT / "examples" / "developer_workflow_local_sandbox_proof_report.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "developer_workflow_local_rollback_summary_packet.generated.json"


def build_developer_workflow_local_rollback_summary_packet(
    *,
    local_sandbox_proof_report: Mapping[str, Any],
    local_sandbox_proof_report_path: Path,
) -> dict[str, Any]:
    """Return a projection-only rollback summary packet."""

    artifacts = local_sandbox_proof_report.get("generated_artifacts", {})
    if not isinstance(artifacts, Mapping):
        artifacts = {}
    artifact_rows = [
        _artifact_row(artifact_id=str(artifact_id), path=str(path))
        for artifact_id, path in sorted(artifacts.items())
        if str(artifact_id).strip() and str(path).strip()
    ]
    return {
        "packet_id": "developer_workflow_local_rollback_summary_packet.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": str(
            local_sandbox_proof_report.get("workflow_run_id") or "developer_workflow_v1_foundation_run"
        ),
        "packet_status": "rollback_ready" if artifact_rows else "rollback_unavailable",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "rollback_execution_performed": False,
        "source_report_path": _path_label(local_sandbox_proof_report_path),
        "generated_artifact_count": len(artifact_rows),
        "rollback_command_preview": [str(row["rollback_command"]) for row in artifact_rows],
        "source_refs": {
            "local_sandbox_proof_report": _path_label(local_sandbox_proof_report_path),
            "builder": "python scripts/build_developer_workflow_local_rollback_summary_packet.py",
            "validator": "python scripts/validate_developer_workflow_local_rollback_summary_packet.py",
        },
        "artifacts": artifact_rows,
    }


def write_developer_workflow_local_rollback_summary_packet(packet: Mapping[str, Any], output_path: Path) -> Path:
    """Write a deterministic rollback summary packet."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _artifact_row(*, artifact_id: str, path: str) -> dict[str, Any]:
    rollback_command = f"Remove-Item -LiteralPath {_powershell_single_quoted(path)} -Force"
    return {
        "artifact_id": artifact_id,
        "path": path,
        "artifact_status": "reported",
        "rollback_action": "delete_generated_artifact",
        "rollback_command": rollback_command,
        "required_confirmation": True,
    }


def _powershell_single_quoted(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


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
    """Parse rollback summary builder arguments."""

    parser = argparse.ArgumentParser(description="Build Developer Workflow local rollback summary packet.")
    parser.add_argument("--proof-report", default=str(DEFAULT_PROOF_REPORT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for rollback summary packet building."""

    args = parse_args(argv)
    try:
        proof_report_path = Path(args.proof_report)
        packet = build_developer_workflow_local_rollback_summary_packet(
            local_sandbox_proof_report=_load_json_object(proof_report_path),
            local_sandbox_proof_report_path=proof_report_path,
        )
        output_path = write_developer_workflow_local_rollback_summary_packet(packet, Path(args.output))
        validation = validate_developer_workflow_local_rollback_summary_packet(
            packet_path=output_path,
            proof_report_path=proof_report_path,
        )
    except ValueError as exc:
        print(f"DEVELOPER WORKFLOW LOCAL ROLLBACK SUMMARY PACKET BUILD INVALID error={exc}")
        return 2
    if not validation.ok:
        print(f"DEVELOPER WORKFLOW LOCAL ROLLBACK SUMMARY PACKET BUILD INVALID errors={list(validation.errors)}")
        return 2
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(f"DEVELOPER WORKFLOW LOCAL ROLLBACK SUMMARY PACKET BUILT path={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

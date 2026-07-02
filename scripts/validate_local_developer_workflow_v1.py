#!/usr/bin/env python3
"""Validate Local Developer Workflow v1 artifacts.

Purpose: fail closed if Local Developer Workflow v1 artifacts drift from
preview-only, no-mutation semantics. Optionally validates the closure packet
emitted by the preview runner.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: software_dev.local_developer_workflow_v1 runner and closure
packet validator.
Invariants: validation rejects any claim of live execution, source mutation,
branch push, pull-request creation, merge, deployment, connector call, or
external write.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for import_root in (REPO_ROOT, MCOI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from software_dev.local_developer_workflow_v1.runner import (  # noqa: E402
    ARTIFACT_FILENAMES,
    build_local_developer_workflow_v1_artifacts,
    validate_local_developer_workflow_v1_artifacts,
)
from software_dev.local_developer_workflow_v1.closure_packet import (  # noqa: E402
    CLOSURE_PACKET_FILENAME,
    validate_local_developer_workflow_closure_packet,
)


DEFAULT_ARTIFACTS = {
    key: REPO_ROOT / ".change_assurance" / filename
    for key, filename in ARTIFACT_FILENAMES.items()
}
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "local_developer_workflow_v1_validation.json"
DEFAULT_CLOSURE_PACKET = REPO_ROOT / ".change_assurance" / CLOSURE_PACKET_FILENAME


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse Local Developer Workflow v1 validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Local Developer Workflow v1 artifacts.")
    parser.add_argument("--repo-status", default=str(DEFAULT_ARTIFACTS["repo_status"]))
    parser.add_argument("--patch-plan", default=str(DEFAULT_ARTIFACTS["patch_plan"]))
    parser.add_argument("--diff-proposal", default=str(DEFAULT_ARTIFACTS["diff_proposal"]))
    parser.add_argument("--test-plan", default=str(DEFAULT_ARTIFACTS["test_plan"]))
    parser.add_argument("--receipt", default=str(DEFAULT_ARTIFACTS["receipt"]))
    parser.add_argument("--approval-request", default=str(DEFAULT_ARTIFACTS["approval_request"]))
    parser.add_argument("--pr-command-preview", default=str(DEFAULT_ARTIFACTS["pr_command_preview"]))
    parser.add_argument("--closure-packet", default=str(DEFAULT_CLOSURE_PACKET))
    parser.add_argument("--require-closure-packet", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--build-if-missing", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for Local Developer Workflow v1 validation."""

    args = parse_args(argv)
    artifact_paths = _artifact_paths(args)
    if args.build_if_missing and any(not path.exists() for path in artifact_paths.values()):
        artifacts = build_local_developer_workflow_v1_artifacts(repo_root=REPO_ROOT)
    else:
        artifacts = {
            key: _load_json_object(path)
            for key, path in artifact_paths.items()
        }
    validation = validate_local_developer_workflow_v1_artifacts(
        artifacts=artifacts,
        artifact_paths=artifact_paths,
    )
    errors = list(validation.errors)
    closure_packet_path = Path(args.closure_packet)
    closure_status = "not_present"
    if closure_packet_path.exists():
        closure_packet = _load_json_object(closure_packet_path)
        closure_validation = validate_local_developer_workflow_closure_packet(
            packet=closure_packet,
            artifacts=artifacts,
            artifact_paths=artifact_paths,
            packet_path=closure_packet_path,
        )
        closure_status = closure_validation.status
        errors.extend(f"closure_packet:{error}" for error in closure_validation.errors)
    elif args.require_closure_packet:
        errors.append(f"closure_packet_missing:{closure_packet_path}")
    ok = validation.ok and not errors
    output_payload = validation.as_dict()
    output_payload["ok"] = ok
    output_payload["errors"] = errors
    output_payload["closure_packet_path"] = str(closure_packet_path)
    output_payload["closure_packet_status"] = closure_status
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(
        json.dumps(output_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.json:
        print(json.dumps(output_payload, indent=2, sort_keys=True))
    elif ok:
        print("LOCAL DEVELOPER WORKFLOW V1 VALID")
    else:
        print(f"LOCAL DEVELOPER WORKFLOW V1 INVALID errors={errors}")
    return 0 if ok or not args.strict else 2


def _artifact_paths(args: argparse.Namespace) -> dict[str, Path]:
    return {
        "repo_status": Path(args.repo_status),
        "patch_plan": Path(args.patch_plan),
        "diff_proposal": Path(args.diff_proposal),
        "test_plan": Path(args.test_plan),
        "receipt": Path(args.receipt),
        "approval_request": Path(args.approval_request),
        "pr_command_preview": Path(args.pr_command_preview),
    }


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"json_parse_failed:{path}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError(f"json_root_must_be_object:{path}")
    return dict(payload)


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run Local Developer Workflow v1 in preview-only mode.

Purpose: generate repo status, patch-plan draft, diff proposal, test plan,
operator receipt, approval request, and PR command preview artifacts.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: software_dev.local_developer_workflow_v1.runner.
Invariants: the runner writes only local JSON proof artifacts and never edits
source files, runs tests, creates branches, opens pull requests, merges,
deploys, calls connectors, or performs external effects.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for import_root in (REPO_ROOT, MCOI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from software_dev.local_developer_workflow_v1.runner import (  # noqa: E402
    ARTIFACT_FILENAMES,
    DEFAULT_ACTOR_ID,
    DEFAULT_CANDIDATE_BRANCH,
    DEFAULT_OBJECTIVE,
    DEFAULT_REPOSITORY_REF,
    DEFAULT_REQUESTED_AT,
    DEFAULT_TARGET_BRANCH,
    DEFAULT_WORKSPACE_ID,
    build_local_developer_workflow_v1_artifacts,
    validate_local_developer_workflow_v1_artifacts,
    write_local_developer_workflow_v1_artifacts,
)


DEFAULT_OUTPUT_DIR = REPO_ROOT / ".change_assurance"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse Local Developer Workflow v1 runner arguments."""

    parser = argparse.ArgumentParser(description="Run Local Developer Workflow v1 preview-only projection.")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--objective", default=DEFAULT_OBJECTIVE)
    parser.add_argument("--actor-id", default=DEFAULT_ACTOR_ID)
    parser.add_argument("--workspace-id", default=DEFAULT_WORKSPACE_ID)
    parser.add_argument("--repository-ref", default=DEFAULT_REPOSITORY_REF)
    parser.add_argument("--requested-at", default=DEFAULT_REQUESTED_AT)
    parser.add_argument("--target-branch", default=DEFAULT_TARGET_BRANCH)
    parser.add_argument("--candidate-branch", default=DEFAULT_CANDIDATE_BRANCH)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for Local Developer Workflow v1."""

    args = parse_args(argv)
    artifacts = build_local_developer_workflow_v1_artifacts(
        repo_root=Path(args.repo_root),
        objective=str(args.objective),
        actor_id=str(args.actor_id),
        workspace_id=str(args.workspace_id),
        repository_ref=str(args.repository_ref),
        requested_at=str(args.requested_at),
        target_branch=str(args.target_branch),
        candidate_branch=str(args.candidate_branch),
        artifact_filenames=ARTIFACT_FILENAMES,
    )
    written_paths = write_local_developer_workflow_v1_artifacts(
        artifacts,
        Path(args.output_dir),
        artifact_filenames=ARTIFACT_FILENAMES,
    )
    validation = validate_local_developer_workflow_v1_artifacts(
        artifacts=artifacts,
        artifact_paths=written_paths,
    )
    output = {
        "ok": validation.ok,
        "errors": list(validation.errors),
        "artifact_paths": {
            key: str(path)
            for key, path in written_paths.items()
        },
        "status": validation.status,
    }
    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
    elif validation.ok:
        print(f"LOCAL DEVELOPER WORKFLOW V1 BUILT output_dir={Path(args.output_dir)}")
    else:
        print(f"LOCAL DEVELOPER WORKFLOW V1 INVALID errors={list(validation.errors)}")
    return 0 if validation.ok or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())

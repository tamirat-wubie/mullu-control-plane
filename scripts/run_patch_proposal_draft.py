#!/usr/bin/env python3
"""Run the standalone patch proposal draft capability.

Purpose: emit a safe diff preview, test plan, rollback plan, risk level, and
approval boundary before file writing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: software_dev.patch_proposal.runner.
Invariants: this runner writes only a local JSON proposal artifact and never
edits source files, runs tests, pushes branches, opens PRs, merges, deploys, or
calls connectors.
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

from software_dev.patch_proposal.runner import (  # noqa: E402
    ARTIFACT_FILENAME,
    DEFAULT_PATCH_PLAN_REF,
    DEFAULT_REQUESTED_AT,
    collect_patch_proposal_draft,
    validate_patch_proposal_draft,
    write_patch_proposal_draft,
)
from software_dev.local_developer_workflow_v1.runner import DEFAULT_OBJECTIVE  # noqa: E402


DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / ARTIFACT_FILENAME


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse patch proposal draft runner arguments."""

    parser = argparse.ArgumentParser(description="Build a preview-only patch proposal draft.")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--objective", default=DEFAULT_OBJECTIVE)
    parser.add_argument("--target-file", action="append", default=[])
    parser.add_argument("--patch-plan-ref", default=DEFAULT_PATCH_PLAN_REF)
    parser.add_argument("--requested-at", default=DEFAULT_REQUESTED_AT)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for patch proposal draft generation."""

    args = parse_args(argv)
    proposal = collect_patch_proposal_draft(
        repo_root=Path(args.repo_root),
        objective=str(args.objective),
        target_files=tuple(args.target_file),
        patch_plan_ref=str(args.patch_plan_ref),
        requested_at=str(args.requested_at),
    )
    output_path = write_patch_proposal_draft(proposal, Path(args.output))
    validation = validate_patch_proposal_draft(proposal, artifact_path=output_path)
    if args.json:
        print(json.dumps({
            "ok": validation.ok,
            "errors": list(validation.errors),
            "proposal_id": validation.proposal_id,
            "proposal_status": validation.proposal_status,
            "artifact_path": str(output_path),
        }, indent=2, sort_keys=True))
    elif validation.ok:
        print(f"PATCH PROPOSAL DRAFT BUILT path={output_path}")
    else:
        print(f"PATCH PROPOSAL DRAFT INVALID errors={list(validation.errors)}")
    return 0 if validation.ok or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())

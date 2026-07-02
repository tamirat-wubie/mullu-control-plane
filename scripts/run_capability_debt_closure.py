#!/usr/bin/env python3
"""Run the capability debt closure artifact projection.

Purpose: emit one read-only capability closure plan, missing-ref view, next
approval action, and closure receipt from the current debt report.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: mcoi/capability_closure/runner.py and capability debt report
runtime projection.
Invariants: this script writes local planning artifacts only; it does not grant
live execution, connector mutation, repository mutation, PR creation, or merge.
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

from capability_closure.runner import (  # noqa: E402
    ARTIFACT_FILENAMES,
    EXAMPLE_ARTIFACT_FILENAMES,
    build_capability_closure_artifacts,
    write_capability_closure_artifacts,
)


DEFAULT_OUTPUT_DIR = REPO_ROOT / ".change_assurance"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse capability debt closure runner arguments."""

    parser = argparse.ArgumentParser(description="Run capability debt closure projection.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--preferred-capability-id", action="append", default=[])
    parser.add_argument("--preferred-category", default="approval")
    parser.add_argument("--foundation-example-names", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for capability debt closure projection."""

    args = parse_args(argv)
    preferred_capability_ids = tuple(args.preferred_capability_id) or None
    filenames = EXAMPLE_ARTIFACT_FILENAMES if args.foundation_example_names else ARTIFACT_FILENAMES
    artifacts = build_capability_closure_artifacts(
        preferred_capability_ids=preferred_capability_ids or (
            "email.send.with_approval",
            "browser.submit",
            "software_dev.pr_candidate.prepare",
            "software_dev.change.run",
            "software_dev.github_patch_plan.draft",
        ),
        preferred_category=str(args.preferred_category),
        artifact_filenames=filenames,
    )
    written_paths = write_capability_closure_artifacts(
        artifacts,
        Path(args.output_dir),
        artifact_filenames=filenames,
    )
    if args.json:
        print(json.dumps({key: str(path) for key, path in written_paths.items()}, indent=2, sort_keys=True))
    else:
        selected = artifacts["capability_closure_plan"]["selected_capability_id"]
        print(f"CAPABILITY CLOSURE ARTIFACTS WRITTEN selected_capability_id={selected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

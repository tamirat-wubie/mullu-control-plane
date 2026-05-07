#!/usr/bin/env python3
"""Governed evolution CLI for repository ChangeCommand certification.

Validates:
  1. A repo diff becomes a typed ChangeCommand.
  2. Blast-radius, invariant, and replay reports are emitted.
  3. A release certificate binds all evidence.
  4. Strict mode fails when required approval or rollback evidence is missing.

Usage:
  python scripts/certify_change.py --base main --head current
  python scripts/certify_change.py --base origin/main --head HEAD --strict
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_PATH = REPO_ROOT / "mcoi"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(MCOI_PATH) not in sys.path:
    sys.path.insert(0, str(MCOI_PATH))

from mcoi_runtime.core.change_assurance import (  # noqa: E402
    certificate_is_acceptable,
    certify_change,
    write_assurance_bundle,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Certify a governed repository change.")
    parser.add_argument("--base", default="main", help="Base git ref for the change diff.")
    parser.add_argument("--head", default="current", help="Head git ref, or 'current' for worktree diff.")
    parser.add_argument("--author-id", default=None, help="Override author identity for ChangeCommand.")
    parser.add_argument("--approval-id", default=None, help="Approval evidence identifier for high-risk changes.")
    parser.add_argument(
        "--rollback-plan-ref",
        default=None,
        help="Rollback or restore evidence identifier for high-risk changes.",
    )
    parser.add_argument("--strict", action="store_true", help="Fail if production assurance evidence is incomplete.")
    parser.add_argument(
        "--repo-root",
        default=str(REPO_ROOT),
        help="Repository root. Defaults to the parent of this script.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    bundle = certify_change(
        repo_root,
        args.base,
        args.head,
        author_id=args.author_id,
        approval_id=args.approval_id,
        rollback_plan_ref=args.rollback_plan_ref,
        strict=args.strict,
    )
    artifact_paths = write_assurance_bundle(repo_root, bundle)
    acceptable = certificate_is_acceptable(bundle.certificate)
    print(f"ChangeCommand: {bundle.command.change_id}")
    print(f"Risk: {bundle.command.risk.value}")
    print(f"Change type: {bundle.command.change_type.value}")
    print(f"Affected files: {len(bundle.command.affected_files)}")
    print(f"Certificate: {bundle.certificate.certificate_id}")
    print("Artifacts:")
    for path in artifact_paths:
        print(f"  - {path.relative_to(repo_root).as_posix()}")
    if args.strict and not acceptable:
        print("Strict certification failed: release certificate is incomplete.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

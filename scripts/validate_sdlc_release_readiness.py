#!/usr/bin/env python3
"""Validate SDLC release and deployment readiness.

Purpose: verify release candidates and deployment candidates do not overclaim
evidence and cannot make production claims without witness proofs.
Governance scope: OCE release field completeness, RAG release-to-deployment
linkage, CDCV claim causality, CQTE readiness gates, UWMA receipts, and PRS
release closure.
Dependencies: Python standard library and scripts/validate_sdlc_artifact.py.
Invariants:
  - Release claims must be evidence-bound.
  - Published production claims require deployment witness and public health.
  - Not-published candidates must keep production claims false.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_sdlc_artifact import (  # noqa: E402
    ARTIFACT_SPEC_BY_KIND,
    load_json_object,
    validate_artifact_record,
    validate_deployment_candidate_record,
    validate_release_candidate_record,
)


def validate_release_deployment_pair(
    release_record: dict[str, object],
    deployment_record: dict[str, object],
    *,
    strict: bool,
) -> list[str]:
    """Validate release and deployment readiness relationship."""

    errors = validate_artifact_record("release_candidate", release_record) + validate_artifact_record(
        "deployment_candidate",
        deployment_record,
    )
    errors.extend(validate_release_candidate_record(release_record, strict=strict))
    errors.extend(validate_deployment_candidate_record(deployment_record, strict=strict))
    if deployment_record.get("release_id") != release_record.get("release_id"):
        errors.append("release_readiness: deployment.release_id must match release")
    if release_record.get("deployment_status") == "not_published":
        if deployment_record.get("public_production_claim") is not False:
            errors.append("release_readiness: not_published release cannot carry production claim")
        public_health = deployment_record.get("public_health")
        if isinstance(public_health, dict) and public_health.get("status") != "not_declared":
            errors.append("release_readiness: not_published release must keep public health not_declared")
    if release_record.get("deployment_status") == "published" and deployment_record.get("public_production_claim") is not True:
        errors.append("release_readiness: published release requires production claim evidence")
    return errors


def validate_contract(
    release_path: Path | None = None,
    deployment_path: Path | None = None,
    *,
    strict: bool = False,
) -> list[str]:
    """Validate the canonical or provided release/deployment artifacts."""

    resolved_release_path = ARTIFACT_SPEC_BY_KIND["release_candidate"].example_path if release_path is None else release_path
    resolved_deployment_path = (
        ARTIFACT_SPEC_BY_KIND["deployment_candidate"].example_path if deployment_path is None else deployment_path
    )
    release_record = load_json_object(resolved_release_path, "SDLC release candidate")
    deployment_record = load_json_object(resolved_deployment_path, "SDLC deployment candidate")
    return validate_release_deployment_pair(release_record, deployment_record, strict=strict)


def main(argv: list[str] | None = None) -> int:
    """Validate SDLC release readiness."""

    parser = argparse.ArgumentParser(description="Validate SDLC release readiness.")
    parser.add_argument("--release", type=Path, help="optional release candidate JSON path")
    parser.add_argument("--deployment", type=Path, help="optional deployment candidate JSON path")
    parser.add_argument("--strict", action="store_true", help="enforce strict readiness controls")
    args = parser.parse_args(argv)

    try:
        errors = validate_contract(args.release, args.deployment, strict=args.strict)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"[FAIL] sdlc-release-readiness-load: {exc}\nSTATUS: failed\n")
        return 1

    if errors:
        for error in errors:
            sys.stderr.write(f"[FAIL] sdlc-release-readiness: {error}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1

    sys.stdout.write("[PASS] sdlc_release_candidate\n")
    sys.stdout.write("[PASS] sdlc_deployment_candidate\n")
    sys.stdout.write("[PASS] sdlc_release_claim_boundary\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

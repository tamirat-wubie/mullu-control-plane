#!/usr/bin/env python3
"""Validate the Foundation Mode public CI window boundary.

Purpose: keep temporary repository-public windows bounded to GitHub Actions
execution and evidence capture during Foundation Mode budget constraints.
Governance scope: source-control visibility, CI execution, proprietary
boundary protection, secret exposure prevention, and public-readiness
separation.
Dependencies: docs/FOUNDATION_PUBLIC_CI_WINDOW_BOUNDARY.md.
Invariants:
  - Validation is read-only.
  - Public visibility is not public readiness.
  - Public CI windows do not authorize public launch, customer exposure,
    production deployment, legal filing, fundraising, or raw secret exposure.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_PUBLIC_CI_WINDOW_BOUNDARY.md"
DEFAULT_WITNESS_PATH = REPO_ROOT / "examples" / "foundation_public_ci_window_boundary_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_public_ci_window_boundary_witness.awaiting_evidence.v1"
EXPECTED_WINDOW_ID = "foundation_public_ci_window.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "public readiness",
    "public launch",
    "customer access",
    "production deployment",
    "legal filing",
    "fundraising readiness",
    "raw secret exposure",
)
EXPECTED_VALIDATOR_COMMANDS = (
    "python scripts/validate_public_repository_surface.py --local-only",
    "python scripts/validate_proprietary_boundary.py",
    "python scripts/validate_release_status.py",
    "python scripts/report_ci_health.py --repo tamirat-wubie/mullu-control-plane --branch main --json",
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "branch",
    "closed_at",
    "closure_decision",
    "customer_access_claimed",
    "exposure_decision",
    "head_sha",
    "opened_at",
    "production_deployment_claimed",
    "public_launch_claimed",
    "public_readiness_claimed",
    "raw_secrets_committed",
    "reason",
    "repo_visibility_after",
    "repo_visibility_before",
    "schema_version",
    "solver_outcome",
    "status",
    "validators",
    "window_id",
    "witness_id",
    "workflow_run_urls",
}

REQUIRED_FRAGMENTS = (
    "Foundation Public CI Window Boundary",
    "temporary CI execution surface",
    "public visibility is not public readiness",
    "Foundation Mode",
    "GitHub Actions execution",
    "no raw secrets",
    "pre-window",
    "open-window",
    "execution-window",
    "close-window",
    "post-window receipt",
    "python scripts/validate_public_repository_surface.py --local-only",
    "python scripts/validate_proprietary_boundary.py",
    "python scripts/validate_release_status.py",
    "python scripts/report_ci_health.py --repo tamirat-wubie/mullu-control-plane --branch main --json",
    "repo_visibility_before",
    "repo_visibility_after",
    "workflow_run_urls",
    "exposure_decision",
    "closure_decision",
    "AwaitingEvidence",
    "../examples/foundation_public_ci_window_boundary_witness.awaiting_evidence.json",
)

FORBIDDEN_FRAGMENTS = (
    "public visibility is public readiness",
    "public visibility equals public readiness",
    "public launch allowed",
    "customer exposure allowed",
    "production deployment allowed",
    "legal filing allowed",
    "fundraising allowed",
    "raw secrets may be printed",
)


@dataclass(frozen=True)
class Finding:
    """A deterministic validation finding for the public CI window boundary."""

    rule_id: str
    message: str


def _normalise(content: str) -> str:
    return " ".join(content.casefold().split())


def validate_document_text(content: str) -> list[Finding]:
    """Validate the public CI window boundary document content."""

    findings: list[Finding] = []
    normalised = _normalise(content)
    for fragment in REQUIRED_FRAGMENTS:
        if _normalise(fragment) not in normalised:
            findings.append(
                Finding(
                    "public_ci_window_required_fragment_missing",
                    f"missing required fragment: {fragment}",
                )
            )
    for fragment in FORBIDDEN_FRAGMENTS:
        if _normalise(fragment) in normalised:
            findings.append(
                Finding(
                    "public_ci_window_forbidden_fragment_present",
                    f"forbidden fragment present: {fragment}",
                )
            )
    return findings


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object with explicit path and type errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return payload


def validate_witness(payload: dict[str, Any]) -> list[Finding]:
    """Validate the committed public CI window AwaitingEvidence witness."""

    findings: list[Finding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            Finding(
                "public_ci_window_witness_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )

    expected_values: dict[str, object] = {
        "witness_id": EXPECTED_WITNESS_ID,
        "window_id": EXPECTED_WINDOW_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "public_readiness_claimed": False,
        "public_launch_claimed": False,
        "customer_access_claimed": False,
        "production_deployment_claimed": False,
        "raw_secrets_committed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                Finding("public_ci_window_witness_value_invalid", f"{key} must be {expected_value!r}")
            )

    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            Finding(
                "public_ci_window_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )

    validators = payload.get("validators")
    if not isinstance(validators, list) or not all(isinstance(item, dict) for item in validators):
        findings.append(Finding("public_ci_window_validators_invalid", "validators must be a list of objects"))
    else:
        observed_commands = tuple(item.get("command") for item in validators)
        observed_states = tuple(item.get("state") for item in validators)
        if observed_commands != EXPECTED_VALIDATOR_COMMANDS:
            findings.append(
                Finding("public_ci_window_validator_commands_invalid", "validator command inventory drifted")
            )
        if observed_states != ("AwaitingEvidence",) * len(EXPECTED_VALIDATOR_COMMANDS):
            findings.append(
                Finding("public_ci_window_validator_states_invalid", "validator states must remain AwaitingEvidence")
            )

    if payload.get("opened_at") is not None or payload.get("closed_at") is not None:
        findings.append(
            Finding(
                "public_ci_window_live_timestamps_invalid",
                "committed witness must not claim a live public CI window timestamp",
            )
        )
    if payload.get("workflow_run_urls") != []:
        findings.append(
            Finding(
                "public_ci_window_workflow_urls_invalid",
                "committed witness must not claim observed live workflow runs",
            )
        )
    return findings


def validate_foundation_public_ci_window_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    witness_path: Path = DEFAULT_WITNESS_PATH,
) -> list[Finding]:
    """Validate the repository-local public CI window boundary artifact."""

    if not doc_path.exists():
        return [
            Finding(
                "public_ci_window_document_missing",
                f"missing public CI window boundary document: {doc_path}",
            )
        ]
    findings = validate_document_text(doc_path.read_text(encoding="utf-8"))
    witness_payload = load_json_object(witness_path, "public CI window boundary witness")
    findings.extend(validate_witness(witness_payload))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the public CI window boundary.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--witness", type=Path, default=DEFAULT_WITNESS_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_public_ci_window_boundary(args.doc, args.witness)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] public_ci_window_boundary_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    print("[PASS] foundation_public_ci_window_boundary")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

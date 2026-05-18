#!/usr/bin/env python3
"""Build and validate governed swarm staging evidence bundles.

Purpose: bind runner preflight evidence and activation witness evidence into one
cross-checked staging activation claim.
Governance scope: deployed commit, runtime bridge, audit-store path, staging URL,
runner readiness, activation outcome, and evidence file references.
Dependencies: governed swarm staging runner preflight validator, activation witness
validator, schemas/governed_swarm_staging_evidence_bundle.schema.json, and jsonschema.
Invariants: bundle closure requires both source artifacts to validate and all
cross-artifact identity, path, URL, and outcome checks to pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_governed_swarm_staging_activation_witness import validate_witness_payload
from scripts.validate_governed_swarm_staging_runner_preflight import validate_runner_preflight_payload
from scripts.validate_schemas import _load_schema, _validate_schema_instance


SCHEMA_PATH = REPO_ROOT / "schemas" / "governed_swarm_staging_evidence_bundle.schema.json"
DEFAULT_RUNNER_PREFLIGHT = REPO_ROOT / "docs" / "governed-swarm-staging-runner-preflight-example.json"
DEFAULT_ACTIVATION_WITNESS = REPO_ROOT / "docs" / "governed-swarm-staging-activation-witness-example.json"
DEFAULT_BUNDLE_OUTPUT = Path(".change_assurance") / "governed_swarm_staging_evidence_bundle.json"
REQUIRED_CHECKS = {
    "runner_preflight_valid",
    "activation_witness_valid",
    "control_plane_commit_match",
    "runtime_path_match",
    "audit_store_path_match",
    "runner_ready",
    "activation_solved",
    "environment_bound",
    "staging_url_bound",
}


def build_staging_evidence_bundle_payload(
    runner_preflight: dict[str, Any],
    activation_witness: dict[str, Any],
    *,
    runner_preflight_ref: str,
    activation_witness_ref: str,
    validated_at: str | None = None,
) -> dict[str, Any]:
    """Build a governed swarm staging evidence bundle from validated source artifacts."""

    runner_errors = validate_runner_preflight_payload(runner_preflight)
    witness_errors = validate_witness_payload(activation_witness)
    check_inputs = [
        (
            "runner_preflight_valid",
            not runner_errors,
            "runner preflight validates" if not runner_errors else "; ".join(runner_errors),
        ),
        (
            "activation_witness_valid",
            not witness_errors,
            "activation witness validates" if not witness_errors else "; ".join(witness_errors),
        ),
        (
            "control_plane_commit_match",
            runner_preflight.get("control_plane_commit") == activation_witness.get("control_plane_commit"),
            f"{runner_preflight.get('control_plane_commit')} == {activation_witness.get('control_plane_commit')}",
        ),
        (
            "runtime_path_match",
            runner_preflight.get("runtime_path") == activation_witness.get("runtime_path"),
            f"{runner_preflight.get('runtime_path')} == {activation_witness.get('runtime_path')}",
        ),
        (
            "audit_store_path_match",
            runner_preflight.get("audit_store_path") == activation_witness.get("audit_store", {}).get("path"),
            f"{runner_preflight.get('audit_store_path')} == {activation_witness.get('audit_store', {}).get('path')}",
        ),
        (
            "runner_ready",
            runner_preflight.get("ready") is True,
            f"runner ready={runner_preflight.get('ready')}",
        ),
        (
            "activation_solved",
            activation_witness.get("outcome") == "SolvedVerified",
            f"activation outcome={activation_witness.get('outcome')}",
        ),
        (
            "environment_bound",
            activation_witness.get("environment") in {"staging", "pilot"},
            f"environment={activation_witness.get('environment')}",
        ),
        (
            "staging_url_bound",
            isinstance(runner_preflight.get("staging_url"), str) and runner_preflight["staging_url"].startswith(("http://", "https://")),
            f"staging_url={runner_preflight.get('staging_url')}",
        ),
    ]
    cross_checks = [{"name": name, "passed": passed, "detail": detail} for name, passed, detail in check_inputs]
    errors = [f"{check['name']}: {check['detail']}" for check in cross_checks if check["passed"] is not True]
    outcome = "SolvedVerified" if not errors else "AwaitingEvidence"

    observed_at = validated_at or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    bundle_fingerprint = hashlib.sha256(
        "|".join(
            [
                runner_preflight_ref,
                activation_witness_ref,
                str(runner_preflight.get("control_plane_commit")),
                str(activation_witness.get("witness_id")),
            ]
        ).encode("utf-8")
    ).hexdigest()[:16]

    return {
        "bundle_id": f"governed-swarm-staging-bundle-{bundle_fingerprint}",
        "validated_at": observed_at,
        "environment": activation_witness.get("environment"),
        "runner_preflight_ref": runner_preflight_ref,
        "activation_witness_ref": activation_witness_ref,
        "control_plane_commit": activation_witness.get("control_plane_commit"),
        "runtime_path": activation_witness.get("runtime_path"),
        "audit_store_path": activation_witness.get("audit_store", {}).get("path"),
        "staging_url": runner_preflight.get("staging_url"),
        "runner_ready": runner_preflight.get("ready"),
        "activation_outcome": activation_witness.get("outcome"),
        "cross_checks": cross_checks,
        "outcome": outcome,
        "errors": errors,
    }


def validate_staging_evidence_bundle_payload(payload: dict[str, Any]) -> list[str]:
    """Return validation errors for a governed swarm staging evidence bundle."""

    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), payload)
    if errors:
        return errors

    check_names = [check["name"] for check in payload["cross_checks"]]
    missing_checks = sorted(REQUIRED_CHECKS - set(check_names))
    duplicate_checks = sorted(name for name in set(check_names) if check_names.count(name) > 1)
    if missing_checks:
        errors.append(f"$.cross_checks missing required checks: {missing_checks}")
    if duplicate_checks:
        errors.append(f"$.cross_checks duplicate checks: {duplicate_checks}")

    failed_checks = [check["name"] for check in payload["cross_checks"] if check["passed"] is not True]
    if payload["outcome"] == "SolvedVerified" and failed_checks:
        errors.append(f"$.outcome cannot be SolvedVerified with failed checks: {failed_checks}")
    if payload["outcome"] == "SolvedVerified" and payload["errors"]:
        errors.append("$.errors must be empty when outcome is SolvedVerified")
    if payload["outcome"] == "AwaitingEvidence" and not (failed_checks or payload["errors"]):
        errors.append("$.outcome cannot be AwaitingEvidence without failed checks or errors")
    if payload["runner_ready"] is True and payload["activation_outcome"] != "SolvedVerified":
        errors.append("$.activation_outcome must be SolvedVerified when runner_ready is true")

    return errors


def validate_staging_evidence_bundle_file(bundle_path: Path) -> list[str]:
    """Load and validate a governed swarm staging evidence bundle file."""

    payload = _load_json_object(bundle_path)
    return validate_staging_evidence_bundle_payload(payload)


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def main() -> int:
    """Build and validate a governed swarm staging evidence bundle from the CLI."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner-preflight", type=Path, default=DEFAULT_RUNNER_PREFLIGHT)
    parser.add_argument("--activation-witness", type=Path, default=DEFAULT_ACTIVATION_WITNESS)
    parser.add_argument("--bundle-output", type=Path, default=DEFAULT_BUNDLE_OUTPUT)
    parser.add_argument("--validated-at", default=None)
    args = parser.parse_args()

    runner_preflight = _load_json_object(args.runner_preflight)
    activation_witness = _load_json_object(args.activation_witness)
    bundle = build_staging_evidence_bundle_payload(
        runner_preflight,
        activation_witness,
        runner_preflight_ref=str(args.runner_preflight),
        activation_witness_ref=str(args.activation_witness),
        validated_at=args.validated_at,
    )
    errors = validate_staging_evidence_bundle_payload(bundle)
    args.bundle_output.parent.mkdir(parents=True, exist_ok=True)
    args.bundle_output.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if errors:
        for error in errors:
            print(f"[FAIL] {error}")
        print(f"WROTE: {args.bundle_output}")
        print("STATUS: failed")
        return 1

    print("[PASS] governed_swarm_staging_evidence_bundle")
    print(f"WROTE: {args.bundle_output}")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

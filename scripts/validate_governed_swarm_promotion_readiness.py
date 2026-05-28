#!/usr/bin/env python3
"""Validate governed swarm promotion readiness.

Purpose: convert a terminal staging evidence bundle into a bounded governed swarm
promotion decision for pilot or production.
Governance scope: staging evidence closure, target environment, production
overclaim prevention, and promotion-blocking output.
Dependencies: scripts.validate_governed_swarm_staging_evidence_bundle,
schemas/governed_swarm_promotion_readiness.schema.json, and jsonschema.
Invariants: pilot readiness requires a solved staging evidence bundle; production
readiness is blocked here and must use the broader production deployment witness.
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

from scripts.validate_governed_swarm_staging_evidence_bundle import validate_staging_evidence_bundle_payload
from scripts.validate_schemas import _load_schema, _validate_schema_instance


SCHEMA_PATH = REPO_ROOT / "schemas" / "governed_swarm_promotion_readiness.schema.json"
DEFAULT_STAGING_BUNDLE = REPO_ROOT / "docs" / "governed-swarm-staging-evidence-bundle-example.json"
DEFAULT_OUTPUT = Path(".change_assurance") / "governed_swarm_promotion_readiness.json"
REQUIRED_CHECKS = {
    "staging_evidence_bundle_valid",
    "staging_evidence_solved",
    "runner_ready_bound",
    "activation_outcome_solved",
    "extension_health_bound",
    "target_environment_allowed",
    "production_witness_required",
}


def build_governed_swarm_promotion_readiness_payload(
    staging_evidence_bundle: dict[str, Any],
    *,
    staging_evidence_bundle_ref: str,
    target_environment: str,
    checked_at: str | None = None,
) -> dict[str, Any]:
    """Build a governed swarm promotion readiness report from a staging evidence bundle."""

    bundle_errors = validate_staging_evidence_bundle_payload(staging_evidence_bundle)
    production_target = target_environment == "production"
    check_inputs = [
        (
            "staging_evidence_bundle_valid",
            not bundle_errors,
            "staging evidence bundle validates" if not bundle_errors else "; ".join(bundle_errors),
        ),
        (
            "staging_evidence_solved",
            staging_evidence_bundle.get("outcome") == "SolvedVerified",
            f"bundle outcome={staging_evidence_bundle.get('outcome')}",
        ),
        (
            "runner_ready_bound",
            staging_evidence_bundle.get("runner_ready") is True,
            f"runner_ready={staging_evidence_bundle.get('runner_ready')}",
        ),
        (
            "activation_outcome_solved",
            staging_evidence_bundle.get("activation_outcome") == "SolvedVerified",
            f"activation_outcome={staging_evidence_bundle.get('activation_outcome')}",
        ),
        (
            "extension_health_bound",
            _extension_health_bound(staging_evidence_bundle.get("extension_health", {})),
            _extension_health_detail(staging_evidence_bundle.get("extension_health", {})),
        ),
        (
            "target_environment_allowed",
            target_environment in {"pilot", "production"},
            f"target_environment={target_environment}",
        ),
        (
            "production_witness_required",
            not production_target,
            "pilot promotion can use staging evidence bundle"
            if not production_target
            else "production promotion requires the public production deployment witness gate",
        ),
    ]
    checks = [{"name": name, "passed": passed, "detail": detail} for name, passed, detail in check_inputs]
    blockers = [check["name"] for check in checks if check["passed"] is not True]
    ready = not blockers
    outcome = "SolvedVerified" if ready else ("GovernanceBlocked" if production_target else "AwaitingEvidence")
    readiness_level = "pilot-ready" if ready else "promotion-blocked"
    observed_at = checked_at or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    fingerprint = hashlib.sha256(
        "|".join(
            [
                staging_evidence_bundle_ref,
                target_environment,
                str(staging_evidence_bundle.get("bundle_id")),
                str(staging_evidence_bundle.get("control_plane_commit")),
            ]
        ).encode("utf-8")
    ).hexdigest()[:16]

    return {
        "readiness_id": f"governed-swarm-promotion-{fingerprint}",
        "checked_at": observed_at,
        "target_environment": target_environment,
        "staging_evidence_bundle_ref": staging_evidence_bundle_ref,
        "control_plane_commit": staging_evidence_bundle.get("control_plane_commit"),
        "runtime_path": staging_evidence_bundle.get("runtime_path"),
        "audit_store_path": staging_evidence_bundle.get("audit_store_path"),
        "staging_url": staging_evidence_bundle.get("staging_url"),
        "extension_health": staging_evidence_bundle.get("extension_health"),
        "ready": ready,
        "readiness_level": readiness_level,
        "outcome": outcome,
        "checks": checks,
        "blockers": blockers,
    }


def validate_governed_swarm_promotion_readiness_payload(payload: dict[str, Any]) -> list[str]:
    """Return validation errors for a governed swarm promotion readiness report."""

    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), payload)
    if errors:
        return errors

    check_names = [check["name"] for check in payload["checks"]]
    missing_checks = sorted(REQUIRED_CHECKS - set(check_names))
    duplicate_checks = sorted(name for name in set(check_names) if check_names.count(name) > 1)
    if missing_checks:
        errors.append(f"$.checks missing required checks: {missing_checks}")
    if duplicate_checks:
        errors.append(f"$.checks duplicate checks: {duplicate_checks}")

    failed_checks = [check["name"] for check in payload["checks"] if check["passed"] is not True]
    if payload["ready"] is True and failed_checks:
        errors.append(f"$.ready cannot be true with failed checks: {failed_checks}")
    if payload["ready"] is True and payload["blockers"]:
        errors.append("$.blockers must be empty when ready is true")
    if payload["ready"] is False and not payload["blockers"]:
        errors.append("$.blockers must name at least one blocked check when ready is false")
    if payload["ready"] is True and payload["outcome"] != "SolvedVerified":
        errors.append("$.outcome must be SolvedVerified when ready is true")
    if payload["target_environment"] == "production" and payload["ready"] is True:
        errors.append("$.ready cannot be true for production in the staging promotion gate")

    return errors


def validate_governed_swarm_promotion_readiness_file(readiness_path: Path) -> list[str]:
    """Load and validate a governed swarm promotion readiness report."""

    return validate_governed_swarm_promotion_readiness_payload(_load_json_object(readiness_path))


def _extension_health_bound(extension_health: dict[str, Any]) -> bool:
    governed_swarm = extension_health.get("governed_swarm", {}) if isinstance(extension_health, dict) else {}
    return (
        isinstance(extension_health, dict)
        and extension_health.get("http_status") == 200
        and extension_health.get("governed") is True
        and governed_swarm.get("registered") is True
        and governed_swarm.get("enabled") is True
        and governed_swarm.get("mounted") is True
        and governed_swarm.get("state") == "mounted"
        and governed_swarm.get("audit_store_configured") is True
    )


def _extension_health_detail(extension_health: dict[str, Any]) -> str:
    governed_swarm = extension_health.get("governed_swarm", {}) if isinstance(extension_health, dict) else {}
    return (
        f"http_status={extension_health.get('http_status') if isinstance(extension_health, dict) else None} "
        f"governed={extension_health.get('governed') if isinstance(extension_health, dict) else None} "
        f"swarm_registered={governed_swarm.get('registered')} "
        f"swarm_enabled={governed_swarm.get('enabled')} "
        f"swarm_mounted={governed_swarm.get('mounted')} "
        f"swarm_state={governed_swarm.get('state')} "
        f"audit_store_configured={governed_swarm.get('audit_store_configured')}"
    )


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for governed swarm promotion readiness validation."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging-evidence-bundle", type=Path, default=DEFAULT_STAGING_BUNDLE)
    parser.add_argument("--target-environment", choices=["pilot", "production"], default="pilot")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--checked-at", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    staging_bundle = _load_json_object(args.staging_evidence_bundle)
    readiness = build_governed_swarm_promotion_readiness_payload(
        staging_bundle,
        staging_evidence_bundle_ref=str(args.staging_evidence_bundle),
        target_environment=args.target_environment,
        checked_at=args.checked_at,
    )
    errors = validate_governed_swarm_promotion_readiness_payload(readiness)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(readiness, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(readiness, indent=2, sort_keys=True))
    elif readiness["ready"]:
        print(f"GOVERNED SWARM PROMOTION READY target={args.target_environment}")
    else:
        print(f"GOVERNED SWARM PROMOTION BLOCKED target={args.target_environment} blockers={readiness['blockers']}")
    if errors:
        for error in errors:
            print(f"[FAIL] {error}", file=sys.stderr)
        return 1
    return 0 if readiness["ready"] or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())

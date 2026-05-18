#!/usr/bin/env python3
"""Validate governed swarm production readiness.

Purpose: require pilot readiness, published deployment witness evidence, and
public production health declaration before governed swarm production claims.
Governance scope: production promotion, public witness closure, health
declaration, and production overclaim prevention.
Dependencies: governed swarm pilot readiness validator, deployment witness
schema, public production health declaration schema, and jsonschema.
Invariants: production readiness cannot pass from staging evidence alone; side
effects remain represented by deployment witness and public health receipts.
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

from scripts.validate_governed_swarm_promotion_readiness import (  # noqa: E402
    validate_governed_swarm_promotion_readiness_payload,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


SCHEMA_PATH = REPO_ROOT / "schemas" / "governed_swarm_production_readiness.schema.json"
DEPLOYMENT_WITNESS_SCHEMA_PATH = REPO_ROOT / "schemas" / "deployment_witness.schema.json"
PUBLIC_HEALTH_DECLARATION_SCHEMA_PATH = (
    REPO_ROOT / "schemas" / "public_production_health_declaration.schema.json"
)
DEFAULT_PILOT_READINESS = REPO_ROOT / "docs" / "governed-swarm-promotion-readiness-example.json"
DEFAULT_DEPLOYMENT_WITNESS = (
    REPO_ROOT / "docs" / "governed-swarm-production-deployment-witness-example.json"
)
DEFAULT_PUBLIC_HEALTH_DECLARATION = (
    REPO_ROOT / "docs" / "governed-swarm-public-production-health-declaration-example.json"
)
DEFAULT_OUTPUT = Path(".change_assurance") / "governed_swarm_production_readiness.json"
REQUIRED_CHECKS = {
    "pilot_readiness_valid",
    "pilot_readiness_ready",
    "deployment_witness_valid",
    "deployment_witness_published",
    "runtime_environment_production",
    "deployment_health_passing",
    "runtime_responsibility_debt_clear",
    "authority_responsibility_debt_clear",
    "public_health_declaration_valid",
    "public_health_declaration_applied",
    "public_health_endpoint_match",
    "production_target_bound",
}


def build_governed_swarm_production_readiness_payload(
    pilot_readiness: dict[str, Any],
    deployment_witness: dict[str, Any],
    public_health_declaration: dict[str, Any],
    *,
    pilot_promotion_readiness_ref: str,
    deployment_witness_ref: str,
    public_health_declaration_ref: str,
    checked_at: str | None = None,
) -> dict[str, Any]:
    """Build a governed swarm production readiness report."""

    pilot_errors = validate_governed_swarm_promotion_readiness_payload(pilot_readiness)
    witness_errors = _validate_schema_instance(
        _load_schema(DEPLOYMENT_WITNESS_SCHEMA_PATH),
        deployment_witness,
    )
    declaration_errors = _validate_schema_instance(
        _load_schema(PUBLIC_HEALTH_DECLARATION_SCHEMA_PATH),
        public_health_declaration,
    )
    witness_endpoint = str(deployment_witness.get("public_health_endpoint", ""))
    declaration_endpoint = str(public_health_declaration.get("public_health_endpoint", ""))
    checks = [
        _check("pilot_readiness_valid", not pilot_errors, _error_detail(pilot_errors, "pilot readiness validates")),
        (
            _check(
                "pilot_readiness_ready",
                pilot_readiness.get("ready") is True
                and pilot_readiness.get("readiness_level") == "pilot-ready",
                f"ready={pilot_readiness.get('ready')} level={pilot_readiness.get('readiness_level')}",
            )
        ),
        _check("deployment_witness_valid", not witness_errors, _error_detail(witness_errors, "deployment witness validates")),
        (
            _check(
                "deployment_witness_published",
                deployment_witness.get("deployment_claim") == "published",
                f"deployment_claim={deployment_witness.get('deployment_claim')}",
            )
        ),
        (
            _check(
                "runtime_environment_production",
                deployment_witness.get("runtime_environment") == "production",
                f"runtime_environment={deployment_witness.get('runtime_environment')}",
            )
        ),
        (
            _check(
                "deployment_health_passing",
                deployment_witness.get("health_http_status") == 200
                and deployment_witness.get("health_status") == "healthy"
                and deployment_witness.get("runtime_witness_status") == "healthy"
                and deployment_witness.get("signature_status") == "verified"
                and deployment_witness.get("conformance_signature_status") == "verified"
                and not deployment_witness.get("errors"),
                "health, runtime witness, signatures, and deployment errors are clear",
            )
        ),
        (
            _check(
                "runtime_responsibility_debt_clear",
                deployment_witness.get("runtime_responsibility_debt_clear") is True,
                f"runtime_responsibility_debt_clear={deployment_witness.get('runtime_responsibility_debt_clear')}",
            )
        ),
        (
            _check(
                "authority_responsibility_debt_clear",
                deployment_witness.get("authority_responsibility_debt_clear") is True
                and deployment_witness.get("authority_overdue_approval_chain_count") == 0
                and deployment_witness.get("authority_overdue_obligation_count") == 0
                and deployment_witness.get("authority_escalated_obligation_count") == 0
                and deployment_witness.get("authority_unowned_high_risk_capability_count") == 0,
                "authority debt and overdue/escalated obligation counts are clear",
            )
        ),
        _check(
            "public_health_declaration_valid",
            not declaration_errors,
            _error_detail(declaration_errors, "public production health declaration validates"),
        ),
        (
            _check(
                "public_health_declaration_applied",
                public_health_declaration.get("dry_run") is False
                and public_health_declaration.get("updated") is True
                and public_health_declaration.get("deployment_witness_state") == "published"
                and not public_health_declaration.get("errors"),
                (
                    f"dry_run={public_health_declaration.get('dry_run')} "
                    f"updated={public_health_declaration.get('updated')} "
                    f"state={public_health_declaration.get('deployment_witness_state')}"
                ),
            )
        ),
        (
            _check(
                "public_health_endpoint_match",
                bool(witness_endpoint)
                and witness_endpoint == declaration_endpoint
                and witness_endpoint.startswith("https://")
                and witness_endpoint.endswith("/health"),
                f"witness_endpoint={witness_endpoint} declaration_endpoint={declaration_endpoint}",
            )
        ),
        _check("production_target_bound", True, "target_environment=production"),
    ]
    blockers = [check["name"] for check in checks if check["passed"] is not True]
    ready = not blockers
    observed_at = checked_at or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    fingerprint = hashlib.sha256(
        "|".join(
            [
                pilot_promotion_readiness_ref,
                deployment_witness_ref,
                public_health_declaration_ref,
                str(pilot_readiness.get("control_plane_commit")),
                witness_endpoint,
            ]
        ).encode("utf-8")
    ).hexdigest()[:16]

    return {
        "readiness_id": f"governed-swarm-production-{fingerprint}",
        "checked_at": observed_at,
        "target_environment": "production",
        "pilot_promotion_readiness_ref": pilot_promotion_readiness_ref,
        "deployment_witness_ref": deployment_witness_ref,
        "public_health_declaration_ref": public_health_declaration_ref,
        "control_plane_commit": pilot_readiness.get("control_plane_commit"),
        "runtime_path": pilot_readiness.get("runtime_path"),
        "audit_store_path": pilot_readiness.get("audit_store_path"),
        "public_health_endpoint": witness_endpoint or declaration_endpoint,
        "ready": ready,
        "readiness_level": "production-ready" if ready else "production-blocked",
        "outcome": "SolvedVerified" if ready else "GovernanceBlocked",
        "checks": checks,
        "blockers": blockers,
    }


def validate_governed_swarm_production_readiness_payload(payload: dict[str, Any]) -> list[str]:
    """Return validation errors for a governed swarm production readiness report."""

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
    if payload["ready"] is True and payload["readiness_level"] != "production-ready":
        errors.append("$.readiness_level must be production-ready when ready is true")
    if payload["ready"] is True and payload["outcome"] != "SolvedVerified":
        errors.append("$.outcome must be SolvedVerified when ready is true")

    return errors


def validate_governed_swarm_production_readiness_file(readiness_path: Path) -> list[str]:
    """Load and validate a governed swarm production readiness report."""

    return validate_governed_swarm_production_readiness_payload(_load_json_object(readiness_path))


def _check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def _error_detail(errors: list[str], pass_detail: str) -> str:
    if not errors:
        return pass_detail
    return f"errors={len(errors)} first={errors[0]}"


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for governed swarm production readiness validation."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-readiness", type=Path, default=DEFAULT_PILOT_READINESS)
    parser.add_argument("--deployment-witness", type=Path, default=DEFAULT_DEPLOYMENT_WITNESS)
    parser.add_argument("--public-health-declaration", type=Path, default=DEFAULT_PUBLIC_HEALTH_DECLARATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--checked-at", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    readiness = build_governed_swarm_production_readiness_payload(
        _load_json_object(args.pilot_readiness),
        _load_json_object(args.deployment_witness),
        _load_json_object(args.public_health_declaration),
        pilot_promotion_readiness_ref=str(args.pilot_readiness),
        deployment_witness_ref=str(args.deployment_witness),
        public_health_declaration_ref=str(args.public_health_declaration),
        checked_at=args.checked_at,
    )
    errors = validate_governed_swarm_production_readiness_payload(readiness)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(readiness, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(readiness, indent=2, sort_keys=True))
    elif readiness["ready"]:
        print("GOVERNED SWARM PRODUCTION READY")
    else:
        print(f"GOVERNED SWARM PRODUCTION BLOCKED blockers={readiness['blockers']}")
    if errors:
        for error in errors:
            print(f"[FAIL] {error}", file=sys.stderr)
        return 1
    return 0 if readiness["ready"] or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())

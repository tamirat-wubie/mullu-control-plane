"""Validate governed swarm staging activation evidence.

Purpose: fail closed when a governed swarm staging activation witness is incomplete.
Governance scope: bundled runtime witness, feature flag, route smoke, audit persistence, rollback.
Dependencies: schemas/governed_swarm_staging_activation_witness.schema.json and jsonschema.
Invariants: staging activation cannot be claimed without bundled runtime witness, enabled flag, audit receipt, and rollback evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance

SCHEMA_PATH = REPO_ROOT / "schemas" / "governed_swarm_staging_activation_witness.schema.json"
REQUIRED_ROUTES = {
    ("POST", "/api/v1/swarm/invoice-runs"),
    ("GET", "/api/v1/swarm/runs/{run_id}"),
    ("GET", "/api/v1/swarm/runs"),
}


def validate_witness_payload(payload: dict[str, Any]) -> list[str]:
    """Return validation errors for a governed swarm staging witness."""

    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), payload)
    if errors:
        return errors

    feature_flags = payload["feature_flags"]
    if payload["runtime_commit"] != payload["control_plane_commit"]:
        errors.append("$.runtime_commit must equal $.control_plane_commit for bundled control-plane runtime")
    if feature_flags["MULLU_GOVERNED_SWARM_RUNTIME_PATH"] != payload["runtime_path"]:
        errors.append("$.feature_flags.MULLU_GOVERNED_SWARM_RUNTIME_PATH must equal $.runtime_path")
    if feature_flags["MULLU_GOVERNED_SWARM_AUDIT_STORE_PATH"] != payload["audit_store"]["path"]:
        errors.append("$.feature_flags.MULLU_GOVERNED_SWARM_AUDIT_STORE_PATH must equal $.audit_store.path")

    observed_routes = {(probe["method"], probe["path"]) for probe in payload["route_probes"]}
    missing_routes = sorted(REQUIRED_ROUTES - observed_routes)
    if missing_routes:
        errors.append(f"$.route_probes missing required routes: {missing_routes}")

    if payload["outcome"] == "SolvedVerified" and payload["errors"]:
        errors.append("$.errors must be empty when outcome is SolvedVerified")
    if payload["outcome"] == "SolvedVerified" and payload["invoice_smoke"]["terminal_status"] != "closed":
        errors.append("$.invoice_smoke.terminal_status must be closed when outcome is SolvedVerified")

    return errors


def validate_witness_file(witness_path: Path) -> list[str]:
    """Load and validate a governed swarm staging witness file."""

    payload = json.loads(witness_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return ["$ must be a JSON object"]
    return validate_witness_payload(payload)


def main() -> int:
    """Validate a governed swarm staging activation witness from the CLI."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--witness",
        type=Path,
        default=REPO_ROOT / "docs" / "governed-swarm-staging-activation-witness-example.json",
    )
    args = parser.parse_args()

    errors = validate_witness_file(args.witness)
    if errors:
        for error in errors:
            print(f"[FAIL] {error}")
        print("STATUS: failed")
        return 1

    print("[PASS] governed_swarm_staging_activation_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

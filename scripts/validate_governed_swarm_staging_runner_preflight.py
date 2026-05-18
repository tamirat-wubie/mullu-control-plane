#!/usr/bin/env python3
"""Validate governed swarm staging runner preflight receipts.

Purpose: fail closed when a saved staging runner preflight receipt cannot prove
the local surfaces required before governed swarm witness collection.
Governance scope: runner URL, deployed commit, runtime bridge, audit store,
readiness outcome, and check-set completeness.
Dependencies: schemas/governed_swarm_staging_runner_preflight.schema.json and jsonschema.
Invariants: ready receipts require all checks to pass; non-ready receipts must
not claim SolvedVerified; every required check must appear exactly once.
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


SCHEMA_PATH = REPO_ROOT / "schemas" / "governed_swarm_staging_runner_preflight.schema.json"
REQUIRED_CHECKS = {
    "staging_url",
    "control_plane_commit",
    "runtime_bridge",
    "audit_store_exists",
    "audit_store_readable",
}


def validate_runner_preflight_payload(payload: dict[str, Any]) -> list[str]:
    """Return validation errors for a governed swarm staging runner preflight receipt."""

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

    all_passed = all(check["passed"] is True for check in payload["checks"])
    if payload["ready"] is True and not all_passed:
        errors.append("$.ready cannot be true unless all checks passed")
    if payload["ready"] is False and payload["outcome"] == "SolvedVerified":
        errors.append("$.outcome cannot be SolvedVerified when ready is false")
    if payload["ready"] is True and payload["outcome"] != "SolvedVerified":
        errors.append("$.outcome must be SolvedVerified when ready is true")

    runtime_bridge_checks = [
        check for check in payload["checks"] if check["name"] == "runtime_bridge" and check["passed"] is True
    ]
    if runtime_bridge_checks and not runtime_bridge_checks[0]["detail"].endswith("/mcoi_runtime/swarm"):
        errors.append("$.checks[runtime_bridge].detail must end with /mcoi_runtime/swarm")

    return errors


def validate_runner_preflight_file(receipt_path: Path) -> list[str]:
    """Load and validate a governed swarm staging runner preflight receipt."""

    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return ["$ must be a JSON object"]
    return validate_runner_preflight_payload(payload)


def main() -> int:
    """Validate a governed swarm staging runner preflight receipt from the CLI."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--receipt",
        type=Path,
        default=REPO_ROOT / "docs" / "governed-swarm-staging-runner-preflight-example.json",
    )
    args = parser.parse_args()

    errors = validate_runner_preflight_file(args.receipt)
    if errors:
        for error in errors:
            print(f"[FAIL] {error}")
        print("STATUS: failed")
        return 1

    print("[PASS] governed_swarm_staging_runner_preflight")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

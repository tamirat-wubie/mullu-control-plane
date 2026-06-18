"""Validate the Foundation Mode read-only first worker path selection.

Purpose: keep the first worker path bounded to local repository inspection.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA]
Dependencies: schemas/read_only_first_worker_path.schema.json and examples/read_only_first_worker_path.foundation.json.
Invariants: first worker selection is read-only, local, no-spend, no-secret, no-network, and path-boundary witnessed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


SCHEMA_PATH = REPO_ROOT / "schemas" / "read_only_first_worker_path.schema.json"
EXAMPLE_PATH = REPO_ROOT / "examples" / "read_only_first_worker_path.foundation.json"
SELECTED_CAPABILITY_ID = "repository.inspect_read_only"
REQUIRED_FALSE_FLAGS = (
    "mutation_allowed",
    "external_network_allowed",
    "secrets_required",
    "spend_required",
)
REQUIRED_RECEIPTS = frozenset(
    {
        "worker_lease_receipt",
        "input_hash_receipt",
        "repository_boundary_witness",
        "read_only_result_receipt",
        "redaction_witness",
        "terminal_closure_or_blocker_receipt",
    }
)
REQUIRED_PROOF_OBLIGATIONS = frozenset(
    {
        "no_write_operation",
        "no_external_network",
        "path_boundary",
        "scan_bounds",
        "secret_redaction",
        "deterministic_traversal",
    }
)


def load_json_payload(path: Path) -> dict[str, Any]:
    """Load a JSON object from path or raise a causal validation error."""
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected JSON object")
    return payload


def validate_read_only_first_worker_path(
    payload: dict[str, Any],
    schema_path: Path = SCHEMA_PATH,
) -> list[str]:
    """Return validation errors for the read-only first worker selection."""
    schema = _load_schema(schema_path)
    errors = _validate_schema_instance(schema, payload)

    if payload.get("selected_capability_id") != SELECTED_CAPABILITY_ID:
        errors.append(
            "selected_capability_id must remain repository.inspect_read_only"
        )

    for flag_name in REQUIRED_FALSE_FLAGS:
        if payload.get(flag_name) is not False:
            errors.append(f"{flag_name} must be false")

    selected_over = payload.get("selected_over")
    if not isinstance(selected_over, list) or len(selected_over) < 2:
        errors.append("selected_over must compare at least two rejected worker paths")

    allowed_inputs = payload.get("allowed_inputs", {})
    if not isinstance(allowed_inputs, dict):
        errors.append("allowed_inputs must be an object")
    else:
        if allowed_inputs.get("max_files", 0) <= 0:
            errors.append("allowed_inputs.max_files must be positive")
        if allowed_inputs.get("max_bytes_per_file", 0) <= 0:
            errors.append("allowed_inputs.max_bytes_per_file must be positive")

    blocked_inputs = payload.get("blocked_inputs", {})
    if not isinstance(blocked_inputs, dict):
        errors.append("blocked_inputs must be an object")
    else:
        for blocked_name in (
            "absolute_paths_outside_repository",
            "raw_secret_values",
            "write_requests",
            "network_targets",
            "tenant_external_resources",
        ):
            if blocked_inputs.get(blocked_name) is not True:
                errors.append(f"blocked_inputs.{blocked_name} must be true")

    receipt_values = set(payload.get("required_receipts", ()))
    missing_receipts = sorted(REQUIRED_RECEIPTS - receipt_values)
    if missing_receipts:
        errors.append(f"required_receipts missing {missing_receipts}")

    obligation_values = set(payload.get("proof_obligations", ()))
    missing_obligations = sorted(REQUIRED_PROOF_OBLIGATIONS - obligation_values)
    if missing_obligations:
        errors.append(f"proof_obligations missing {missing_obligations}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--path",
        type=Path,
        default=EXAMPLE_PATH,
        help="Path to the read-only first worker selection JSON.",
    )
    args = parser.parse_args()

    try:
        payload = load_json_payload(args.path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"read-only first worker path validation failed: {exc}")
        return 1

    errors = validate_read_only_first_worker_path(payload)
    if errors:
        for error in errors:
            print(error)
        return 1

    print(
        "read-only first worker path ok: "
        f"{payload['selection_id']} -> {payload['selected_capability_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

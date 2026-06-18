"""Validate the Foundation Mode read-only search worker path selection.

Purpose: keep local knowledge search bounded to read-only, evidence-only
retrieval under a SearchDecisionReceipt.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA]
Dependencies: schemas/read_only_search_worker_path.schema.json and
examples/read_only_search_worker_path.foundation.json.
Invariants: local search does not admit mutation, web/network access, secrets,
spend, or retrieved instruction authority.
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


SCHEMA_PATH = REPO_ROOT / "schemas" / "read_only_search_worker_path.schema.json"
EXAMPLE_PATH = REPO_ROOT / "examples" / "read_only_search_worker_path.foundation.json"
SELECTED_CAPABILITY_ID = "enterprise.knowledge_search"
REQUIRED_FALSE_FLAGS = (
    "mutation_allowed",
    "external_network_allowed",
    "secrets_required",
    "spend_required",
)
REQUIRED_RECEIPTS = frozenset(
    {
        "search_decision_receipt",
        "worker_lease_receipt",
        "input_hash_receipt",
        "source_boundary_witness",
        "evidence_only_retrieval_witness",
        "read_only_result_receipt",
        "redaction_witness",
        "terminal_closure_or_blocker_receipt",
    }
)
REQUIRED_PROOF_OBLIGATIONS = frozenset(
    {
        "no_write_operation",
        "no_external_network",
        "source_path_boundary",
        "search_decision_receipt_required",
        "evidence_only_retrieval",
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


def validate_read_only_search_worker_path(
    payload: dict[str, Any],
    schema_path: Path = SCHEMA_PATH,
) -> list[str]:
    """Return validation errors for the read-only search worker path."""
    schema = _load_schema(schema_path)
    errors = _validate_schema_instance(schema, payload)

    if payload.get("selected_capability_id") != SELECTED_CAPABILITY_ID:
        errors.append("selected_capability_id must remain enterprise.knowledge_search")
    if payload.get("retrieval_authority") != "evidence_only":
        errors.append("retrieval_authority must remain evidence_only")
    if payload.get("search_decision_receipt_required") is not True:
        errors.append("search_decision_receipt_required must be true")

    for flag_name in REQUIRED_FALSE_FLAGS:
        if payload.get(flag_name) is not False:
            errors.append(f"{flag_name} must be false")

    source_scope = payload.get("source_scope", {})
    if not isinstance(source_scope, dict):
        errors.append("source_scope must be an object")
    else:
        if source_scope.get("web_search_allowed") is not False:
            errors.append("source_scope.web_search_allowed must be false")
        supported_extensions = source_scope.get("supported_extensions", [])
        if not isinstance(supported_extensions, list) or ".md" not in supported_extensions:
            errors.append("source_scope.supported_extensions must include .md")

    blocked_inputs = payload.get("blocked_inputs", {})
    if not isinstance(blocked_inputs, dict):
        errors.append("blocked_inputs must be an object")
    else:
        for blocked_name in (
            "absolute_paths_outside_knowledge_root",
            "raw_secret_values",
            "write_requests",
            "network_targets",
            "tenant_external_resources",
            "web_search_requests",
            "retrieved_instruction_authority",
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
        help="Path to the read-only search worker selection JSON.",
    )
    args = parser.parse_args()

    try:
        payload = load_json_payload(args.path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"read-only search worker path validation failed: {exc}")
        return 1

    errors = validate_read_only_search_worker_path(payload)
    if errors:
        for error in errors:
            print(error)
        return 1

    print(
        "read-only search worker path ok: "
        f"{payload['selection_id']} -> {payload['selected_capability_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

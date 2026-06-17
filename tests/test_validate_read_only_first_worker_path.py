"""Tests for the Foundation Mode read-only first worker path validator.

Purpose: prove the first worker selection remains local, read-only, and receipt-bound.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: scripts.validate_read_only_first_worker_path.
Invariants: repository inspection is selected before mutation, network, secret, or spend-bearing workers.
"""

from __future__ import annotations

from copy import deepcopy

from scripts.validate_read_only_first_worker_path import (
    EXAMPLE_PATH,
    REQUIRED_PROOF_OBLIGATIONS,
    load_json_payload,
    validate_read_only_first_worker_path,
)


def test_read_only_first_worker_path_example_passes() -> None:
    payload = load_json_payload(EXAMPLE_PATH)
    errors = validate_read_only_first_worker_path(payload)

    assert errors == []
    assert payload["selected_capability_id"] == "repository.inspect_read_only"
    assert payload["mutation_allowed"] is False
    assert "path_boundary" in payload["proof_obligations"]


def test_read_only_first_worker_path_rejects_mutation_authority() -> None:
    payload = load_json_payload(EXAMPLE_PATH)
    mutated_payload = deepcopy(payload)
    mutated_payload["mutation_allowed"] = True

    errors = validate_read_only_first_worker_path(mutated_payload)

    assert errors
    assert any("mutation_allowed" in error for error in errors)
    assert mutated_payload["selected_capability_id"] == "repository.inspect_read_only"
    assert "no_write_operation" in mutated_payload["proof_obligations"]


def test_read_only_first_worker_path_rejects_missing_path_boundary() -> None:
    payload = load_json_payload(EXAMPLE_PATH)
    mutated_payload = deepcopy(payload)
    mutated_payload["proof_obligations"] = [
        obligation
        for obligation in REQUIRED_PROOF_OBLIGATIONS
        if obligation != "path_boundary"
    ]

    errors = validate_read_only_first_worker_path(mutated_payload)

    assert errors
    assert any("path_boundary" in error for error in errors)
    assert mutated_payload["mutation_allowed"] is False
    assert mutated_payload["external_network_allowed"] is False

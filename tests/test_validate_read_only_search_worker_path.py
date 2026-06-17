"""Tests for the Foundation Mode read-only search worker path validator.

Purpose: prove the search worker selection remains local, read-only,
evidence-only, and receipt-gated.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: scripts.validate_read_only_search_worker_path.
Invariants: local search does not admit mutation, network, secrets, spend, or
retrieved instruction authority.
"""

from __future__ import annotations

from copy import deepcopy

from scripts.validate_read_only_search_worker_path import (
    EXAMPLE_PATH,
    REQUIRED_PROOF_OBLIGATIONS,
    load_json_payload,
    validate_read_only_search_worker_path,
)


def test_read_only_search_worker_path_example_passes() -> None:
    payload = load_json_payload(EXAMPLE_PATH)
    errors = validate_read_only_search_worker_path(payload)

    assert errors == []
    assert payload["selected_capability_id"] == "enterprise.knowledge_search"
    assert payload["retrieval_authority"] == "evidence_only"
    assert payload["search_decision_receipt_required"] is True
    assert payload["external_network_allowed"] is False


def test_read_only_search_worker_path_rejects_web_retrieval() -> None:
    payload = load_json_payload(EXAMPLE_PATH)
    mutated_payload = deepcopy(payload)
    mutated_payload["source_scope"]["web_search_allowed"] = True

    errors = validate_read_only_search_worker_path(mutated_payload)

    assert errors
    assert any("web_search_allowed" in error for error in errors)
    assert mutated_payload["selected_capability_id"] == "enterprise.knowledge_search"
    assert mutated_payload["mutation_allowed"] is False


def test_read_only_search_worker_path_rejects_missing_decision_receipt_obligation() -> None:
    payload = load_json_payload(EXAMPLE_PATH)
    mutated_payload = deepcopy(payload)
    mutated_payload["proof_obligations"] = [
        obligation
        for obligation in REQUIRED_PROOF_OBLIGATIONS
        if obligation != "search_decision_receipt_required"
    ]

    errors = validate_read_only_search_worker_path(mutated_payload)

    assert errors
    assert any("search_decision_receipt_required" in error for error in errors)
    assert mutated_payload["retrieval_authority"] == "evidence_only"
    assert mutated_payload["spend_required"] is False

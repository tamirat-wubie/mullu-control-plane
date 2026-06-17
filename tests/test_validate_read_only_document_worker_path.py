"""Tests for the Foundation Mode read-only document worker path validator.

Purpose: prove the document worker selection remains local, read-only, and
format-allowlisted.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: scripts.validate_read_only_document_worker_path.
Invariants: document inspection does not admit mutation, network, secrets,
spend, or rich binary parsing.
"""

from __future__ import annotations

from copy import deepcopy

from scripts.validate_read_only_document_worker_path import (
    EXAMPLE_PATH,
    REQUIRED_PROOF_OBLIGATIONS,
    load_json_payload,
    validate_read_only_document_worker_path,
)


def test_read_only_document_worker_path_example_passes() -> None:
    payload = load_json_payload(EXAMPLE_PATH)
    errors = validate_read_only_document_worker_path(payload)

    assert errors == []
    assert payload["selected_capability_id"] == "document.inspect_read_only"
    assert payload["mutation_allowed"] is False
    assert payload["parser_scope"]["rich_document_parsing_allowed"] is False
    assert ".md" in payload["parser_scope"]["supported_extensions"]


def test_read_only_document_worker_path_rejects_rich_document_parsing() -> None:
    payload = load_json_payload(EXAMPLE_PATH)
    mutated_payload = deepcopy(payload)
    mutated_payload["parser_scope"]["rich_document_parsing_allowed"] = True

    errors = validate_read_only_document_worker_path(mutated_payload)

    assert errors
    assert any("rich_document_parsing_allowed" in error for error in errors)
    assert mutated_payload["selected_capability_id"] == "document.inspect_read_only"
    assert mutated_payload["mutation_allowed"] is False


def test_read_only_document_worker_path_rejects_missing_format_allowlist() -> None:
    payload = load_json_payload(EXAMPLE_PATH)
    mutated_payload = deepcopy(payload)
    mutated_payload["proof_obligations"] = [
        obligation
        for obligation in REQUIRED_PROOF_OBLIGATIONS
        if obligation != "format_allowlist"
    ]

    errors = validate_read_only_document_worker_path(mutated_payload)

    assert errors
    assert any("format_allowlist" in error for error in errors)
    assert mutated_payload["external_network_allowed"] is False
    assert mutated_payload["spend_required"] is False

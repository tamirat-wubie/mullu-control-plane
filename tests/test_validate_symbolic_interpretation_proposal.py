"""Tests for symbolic interpretation proposal validation.

Purpose: verify proposal-only interpretation evidence cannot grant execution
or override deterministic request interpretation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_symbolic_interpretation_proposal.
Invariants: no deterministic override, action authority, or execution grant.
"""

from __future__ import annotations

import json

from scripts.validate_symbolic_interpretation_proposal import (
    DEFAULT_EXAMPLE,
    DEFAULT_SCHEMA,
    validate_symbolic_interpretation_proposal,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def _mutated_payload(**updates: object) -> dict[str, object]:
    payload = json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))
    payload.update(updates)
    return payload


def _write_payload(tmp_path, payload: dict[str, object]):
    path = tmp_path / "symbolic_interpretation_proposal.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_default_symbolic_interpretation_proposal_is_valid() -> None:
    result = validate_symbolic_interpretation_proposal()

    assert result.valid is True
    assert result.errors == ()
    assert result.validation_status == "accepted_as_proposal"


def test_default_example_matches_schema() -> None:
    schema = _load_schema(DEFAULT_SCHEMA)
    payload = json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))
    errors = _validate_schema_instance(schema, payload)

    assert errors == []
    assert payload["authority_level"] == "proposal_only"
    assert payload["execution_allowed"] is False
    assert payload["private_payload_included"] is False
    assert payload["secret_values_serialized"] is False
    assert payload["raw_message_hash"].startswith("sha256:")


def test_rejects_execution_authority(tmp_path) -> None:
    path = _write_payload(tmp_path, _mutated_payload(execution_allowed=True))
    result = validate_symbolic_interpretation_proposal(path=path)

    assert result.valid is False
    assert result.errors
    assert any("execution_allowed" in error for error in result.errors)


def test_rejects_deterministic_override(tmp_path) -> None:
    path = _write_payload(tmp_path, _mutated_payload(deterministic_override_allowed=True))
    result = validate_symbolic_interpretation_proposal(path=path)

    assert result.valid is False
    assert result.errors
    assert any("deterministic_override_allowed" in error for error in result.errors)


def test_rejected_status_requires_reason(tmp_path) -> None:
    path = _write_payload(tmp_path, _mutated_payload(validation_status="rejected", rejected_reasons=[]))
    result = validate_symbolic_interpretation_proposal(path=path)

    assert result.valid is False
    assert "rejected proposal must include rejected_reasons" in result.errors
    assert result.validation_status == "rejected"


def test_rejects_private_payload_serialization(tmp_path) -> None:
    path = _write_payload(tmp_path, _mutated_payload(private_payload_included=True))
    result = validate_symbolic_interpretation_proposal(path=path)

    assert result.valid is False
    assert result.errors
    assert any("private_payload_included" in error for error in result.errors)


def test_rejects_secret_value_serialization(tmp_path) -> None:
    path = _write_payload(tmp_path, _mutated_payload(secret_values_serialized=True))
    result = validate_symbolic_interpretation_proposal(path=path)

    assert result.valid is False
    assert result.errors
    assert any("secret_values_serialized" in error for error in result.errors)


def test_rejects_raw_payload_fields(tmp_path) -> None:
    payload = _mutated_payload(raw_message="send this private body")
    path = _write_payload(tmp_path, payload)
    result = validate_symbolic_interpretation_proposal(path=path)

    assert result.valid is False
    assert result.errors
    assert any("Additional properties" in error or "raw_message" in error for error in result.errors)


def test_rejects_malformed_hashes(tmp_path) -> None:
    path = _write_payload(tmp_path, _mutated_payload(raw_message_hash="plain-private-message"))
    result = validate_symbolic_interpretation_proposal(path=path)

    assert result.valid is False
    assert result.errors
    assert any("raw_message_hash" in error or "sha256" in error for error in result.errors)


def test_rejects_inconsistent_comparison_state(tmp_path) -> None:
    path = _write_payload(
        tmp_path,
        _mutated_payload(comparison_result="rejected_before_comparison", validation_status="accepted_as_proposal"),
    )
    result = validate_symbolic_interpretation_proposal(path=path)

    assert result.valid is False
    assert result.errors
    assert any("rejected_before_comparison" in error for error in result.errors)

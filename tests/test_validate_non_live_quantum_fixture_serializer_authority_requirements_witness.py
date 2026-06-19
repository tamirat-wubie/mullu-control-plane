"""Test the non-live quantum fixture serializer authority requirements validator.

Purpose: verify the future-authority requirements-only contract.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: foundation example JSON and authority requirements validator.
Invariants: no serializer implementation, no serializer execution, no serialized
artifact, no canonical bytes, no simulator input or runtime invocation, no
result materialization, and no terminal closure.
"""

from __future__ import annotations

import json
import pathlib

from scripts.validate_non_live_quantum_fixture_serializer_authority_requirements_witness import (
    validate_payload,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "non_live_quantum_fixture_serializer_authority_requirements_witness.foundation.json"


def _payload() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_serializer_authority_requirements_example_is_valid() -> None:
    payload = _payload()

    errors = validate_payload(payload)

    assert errors == []
    assert payload["requirements_only"] is True
    assert payload["authority_granted"] is False
    assert len(payload["authority_requirements"]) == 9


def test_rejects_serializer_implementation_authority() -> None:
    payload = _payload()
    payload["denied_authorities"]["serializer_implementation_enabled"] = True

    errors = validate_payload(payload)

    assert "denied_authorities.serializer_implementation_enabled must be false" in errors
    assert payload["denied_authorities"]["serializer_implementation_enabled"] is True
    assert payload["effect_boundary"]["implementation_file_written"] is False


def test_rejects_implementation_file_write_effect() -> None:
    payload = _payload()
    payload["effect_boundary"]["implementation_file_written"] = True

    errors = validate_payload(payload)

    assert "effect_boundary.implementation_file_written must be false" in errors
    assert payload["effect_boundary"]["implementation_file_written"] is True
    assert payload["authority_requirements_boundary"]["implementation_allowed"] is False


def test_rejects_artifact_write_authority() -> None:
    payload = _payload()
    payload["authority_requirements_boundary"]["artifact_writes_allowed"] = True

    errors = validate_payload(payload)

    assert "authority_requirements_boundary.artifact_writes_allowed must be false" in errors
    assert payload["authority_requirements_boundary"]["artifact_writes_allowed"] is True
    assert payload["effect_boundary"]["serialized_artifact_written"] is False


def test_rejects_current_witness_satisfying_future_authority() -> None:
    payload = _payload()
    payload["authority_requirements"][0]["current_witness_satisfies_authority"] = True

    errors = validate_payload(payload)

    assert "authority_requirements[0].current_witness_satisfies_authority must be false" in errors
    assert payload["authority_requirements"][0]["current_witness_satisfies_authority"] is True
    assert payload["authority_requirements"][0]["future_evidence_required"] is True


def test_rejects_missing_future_evidence_requirement() -> None:
    payload = _payload()
    payload["authority_requirements"][1]["future_evidence_required"] = False

    errors = validate_payload(payload)

    assert "authority_requirements[1].future_evidence_required must be true" in errors
    assert payload["authority_requirements"][1]["future_evidence_required"] is False
    assert payload["authority_granted"] is False


def test_rejects_non_null_implementation_path() -> None:
    payload = _payload()
    payload["authority_requirements_boundary"]["implementation_file_path"] = "scripts/serialize_quantum_fixture.py"

    errors = validate_payload(payload)

    assert "authority_requirements_boundary.implementation_file_path must be null" in errors
    assert payload["authority_requirements_boundary"]["implementation_file_path"].endswith(".py")
    assert payload["authority_requirements_boundary"]["requires_separate_pr"] is True


def test_rejects_missing_operator_authorization_gate() -> None:
    payload = _payload()
    payload["required_authority_gates"] = [
        gate for gate in payload["required_authority_gates"] if gate != "OperatorAuthorizationGate"
    ]

    errors = validate_payload(payload)

    assert any("OperatorAuthorizationGate" in error for error in errors)
    assert "OperatorAuthorizationGate" not in payload["required_authority_gates"]
    assert len(payload["required_authority_gates"]) == 13


def test_rejects_unknown_requirement_category() -> None:
    payload = _payload()
    payload["authority_requirements"][2]["category"] = "runtime_execution_requirement"

    errors = validate_payload(payload)

    assert "authority_requirements[2].category must reference an allowed requirement category" in errors
    assert payload["authority_requirements"][2]["category"] == "runtime_execution_requirement"
    assert "runtime_execution_requirement" not in payload["allowed_requirement_categories"]


def test_rejects_duplicate_requirement_ids() -> None:
    payload = _payload()
    payload["authority_requirements"][1]["requirement_id"] = payload["authority_requirements"][0]["requirement_id"]

    errors = validate_payload(payload)

    assert "authority_requirements.requirement_id values must be unique" in errors
    assert payload["authority_requirements"][0]["requirement_id"] == payload["authority_requirements"][1]["requirement_id"]
    assert len(payload["authority_requirements"]) == 9


def test_rejects_missing_serializer_boundary_related_witness() -> None:
    payload = _payload()
    payload["related_witness_refs"] = [
        "non_live_openqasm_export_planning_witness",
        "non_live_local_quantum_simulator_boundary_witness",
        "non_live_quantum_fixture_catalog_witness"
    ]

    errors = validate_payload(payload)

    assert any("non_live_quantum_fixture_serializer_boundary_witness" in error for error in errors)
    assert "non_live_quantum_fixture_serializer_boundary_witness" not in payload["related_witness_refs"]
    assert payload["serializer_boundary_witness_required"] is True

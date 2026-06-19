"""Test the non-live quantum fixture serializer boundary witness validator.

Purpose: verify the descriptor-only fixture serializer planning contract.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: foundation example JSON and serializer boundary validator.
Invariants: no serializer execution, no serialized fixture artifacts, no
canonical bytes, no simulator input or runtime invocation, no result
materialization, and no terminal closure.
"""

from __future__ import annotations

import json
import pathlib

from scripts.validate_non_live_quantum_fixture_serializer_boundary_witness import validate_payload

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "non_live_quantum_fixture_serializer_boundary_witness.foundation.json"


def _payload() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_non_live_quantum_fixture_serializer_boundary_example_is_valid() -> None:
    payload = _payload()

    errors = validate_payload(payload)

    assert errors == []
    assert payload["planning_only"] is True
    assert payload["serializer_boundary"]["serializer_execution_allowed"] is False
    assert len(payload["serializer_profiles"]) == 4


def test_rejects_serializer_execution_authority() -> None:
    payload = _payload()
    payload["denied_authorities"]["fixture_serializer_execution_enabled"] = True

    errors = validate_payload(payload)

    assert "denied_authorities.fixture_serializer_execution_enabled must be false" in errors
    assert payload["denied_authorities"]["fixture_serializer_execution_enabled"] is True
    assert payload["effect_boundary"]["serializer_executed"] is False


def test_rejects_serialized_artifact_write_effect() -> None:
    payload = _payload()
    payload["effect_boundary"]["serialized_artifact_written"] = True

    errors = validate_payload(payload)

    assert "effect_boundary.serialized_artifact_written must be false" in errors
    assert payload["effect_boundary"]["serialized_artifact_written"] is True
    assert payload["serializer_boundary"]["serialized_artifact_allowed"] is False


def test_rejects_simulator_input_serialization_effect() -> None:
    payload = _payload()
    payload["effect_boundary"]["simulator_input_serialized"] = True

    errors = validate_payload(payload)

    assert "effect_boundary.simulator_input_serialized must be false" in errors
    assert payload["effect_boundary"]["simulator_input_serialized"] is True
    assert payload["denied_authorities"]["simulator_input_serialization_enabled"] is False


def test_rejects_canonical_bytes_materialization() -> None:
    payload = _payload()
    payload["effect_boundary"]["canonical_bytes_materialized"] = True

    errors = validate_payload(payload)

    assert "effect_boundary.canonical_bytes_materialized must be false" in errors
    assert payload["effect_boundary"]["canonical_bytes_materialized"] is True
    assert payload["serializer_boundary"]["canonical_bytes_allowed"] is False


def test_rejects_boundary_output_path_before_future_authority() -> None:
    payload = _payload()
    payload["serializer_boundary"]["output_path"] = "fixtures/quantum/serialized/identity.json"

    errors = validate_payload(payload)

    assert "serializer_boundary.output_path must be null" in errors
    assert payload["serializer_boundary"]["output_path"].endswith(".json")
    assert payload["serializer_boundary"]["requires_future_serializer_schema"] is True


def test_rejects_profile_serialized_output_permission() -> None:
    payload = _payload()
    payload["serializer_profiles"][0]["denied_serialized_output"] = False

    errors = validate_payload(payload)

    assert "serializer_profiles[0].denied_serialized_output must be true" in errors
    assert payload["serializer_profiles"][0]["denied_serialized_output"] is False
    assert payload["serializer_profiles"][0]["future_authority_required"] is True


def test_rejects_duplicate_serializer_profile_ids() -> None:
    payload = _payload()
    payload["serializer_profiles"][1]["profile_id"] = payload["serializer_profiles"][0]["profile_id"]

    errors = validate_payload(payload)

    assert "serializer_profiles.profile_id values must be unique" in errors
    assert payload["serializer_profiles"][0]["profile_id"] == payload["serializer_profiles"][1]["profile_id"]
    assert len(payload["serializer_profiles"]) == 4


def test_rejects_missing_no_canonical_bytes_gate() -> None:
    payload = _payload()
    payload["required_serializer_gates"] = [
        gate for gate in payload["required_serializer_gates"] if gate != "NoCanonicalBytesGate"
    ]

    errors = validate_payload(payload)

    assert any("NoCanonicalBytesGate" in error for error in errors)
    assert "NoCanonicalBytesGate" not in payload["required_serializer_gates"]
    assert len(payload["required_serializer_gates"]) == 11


def test_rejects_profile_allowed_metadata_overlap_with_denied_payload() -> None:
    payload = _payload()
    payload["serializer_profiles"][0]["allowed_metadata_fields"].append("runtime_payload")

    errors = validate_payload(payload)

    assert any("allowed metadata overlaps denied payload fields" in error for error in errors)
    assert "runtime_payload" in payload["serializer_profiles"][0]["allowed_metadata_fields"]
    assert "runtime_payload" in payload["serializer_profiles"][0]["denied_payload_fields"]


def test_rejects_missing_fixture_catalog_related_witness() -> None:
    payload = _payload()
    payload["related_witness_refs"] = ["non_live_openqasm_export_planning_witness"]

    errors = validate_payload(payload)

    assert any("non_live_quantum_fixture_catalog_witness" in error for error in errors)
    assert "non_live_quantum_fixture_catalog_witness" not in payload["related_witness_refs"]
    assert payload["fixture_catalog_witness_required"] is True

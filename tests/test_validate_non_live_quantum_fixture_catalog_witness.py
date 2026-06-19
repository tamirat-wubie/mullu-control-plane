"""Test the non-live quantum fixture catalog witness validator.

Purpose: verify the deterministic fixture catalog planning-only contract.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: foundation example JSON and fixture catalog validator.
Invariants: no executable fixture generation, no source emission, no simulator
input or runtime invocation, no result materialization, and no terminal closure.
"""

from __future__ import annotations

import json
import pathlib

from scripts.validate_non_live_quantum_fixture_catalog_witness import validate_payload

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "non_live_quantum_fixture_catalog_witness.foundation.json"


def _payload() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_non_live_quantum_fixture_catalog_witness_example_is_valid() -> None:
    payload = _payload()

    errors = validate_payload(payload)

    assert errors == []
    assert payload["planning_only"] is True
    assert payload["fixture_catalog"]["executable_artifacts_allowed"] is False
    assert len(payload["fixture_blueprints"]) == 6


def test_rejects_executable_fixture_generation_authority() -> None:
    payload = _payload()
    payload["denied_authorities"]["executable_fixture_generation_enabled"] = True

    errors = validate_payload(payload)

    assert "denied_authorities.executable_fixture_generation_enabled must be false" in errors
    assert payload["denied_authorities"]["executable_fixture_generation_enabled"] is True
    assert payload["effect_boundary"]["executable_fixture_written"] is False


def test_rejects_source_text_emission_effect() -> None:
    payload = _payload()
    payload["effect_boundary"]["openqasm_source_text_emitted"] = True

    errors = validate_payload(payload)

    assert "effect_boundary.openqasm_source_text_emitted must be false" in errors
    assert payload["effect_boundary"]["openqasm_source_text_emitted"] is True
    assert payload["fixture_catalog"]["source_text_allowed"] is False


def test_rejects_simulator_input_generation_effect() -> None:
    payload = _payload()
    payload["effect_boundary"]["simulator_input_written"] = True

    errors = validate_payload(payload)

    assert "effect_boundary.simulator_input_written must be false" in errors
    assert payload["effect_boundary"]["simulator_input_written"] is True
    assert payload["denied_authorities"]["simulator_input_generation_enabled"] is False


def test_rejects_fixture_blueprint_runtime_result() -> None:
    payload = _payload()
    payload["fixture_blueprints"][0]["denied_runtime_result"] = False

    errors = validate_payload(payload)

    assert "fixture_blueprints[0].denied_runtime_result must be true" in errors
    assert payload["fixture_blueprints"][0]["denied_runtime_result"] is False
    assert payload["fixture_catalog"]["requires_no_execution_result"] is True


def test_rejects_duplicate_fixture_ids() -> None:
    payload = _payload()
    payload["fixture_blueprints"][1]["fixture_id"] = payload["fixture_blueprints"][0]["fixture_id"]

    errors = validate_payload(payload)

    assert "fixture_blueprints.fixture_id values must be unique" in errors
    assert payload["fixture_blueprints"][0]["fixture_id"] == payload["fixture_blueprints"][1]["fixture_id"]
    assert len(payload["fixture_blueprints"]) == 6


def test_rejects_missing_no_executable_artifact_gate() -> None:
    payload = _payload()
    payload["required_fixture_gates"] = [
        gate for gate in payload["required_fixture_gates"] if gate != "NoExecutableArtifactGate"
    ]

    errors = validate_payload(payload)

    assert any("NoExecutableArtifactGate" in error for error in errors)
    assert "NoExecutableArtifactGate" not in payload["required_fixture_gates"]
    assert len(payload["required_fixture_gates"]) == 11


def test_rejects_allowed_and_denied_fixture_overlap() -> None:
    payload = _payload()
    payload["allowed_fixture_types"].append("simulator_input_blob")

    errors = validate_payload(payload)

    assert any("allowed fixture types overlap denied fixture contents" in error for error in errors)
    assert "simulator_input_blob" in payload["allowed_fixture_types"]
    assert "simulator_input_blob" in payload["denied_fixture_contents"]


def test_rejects_executable_artifact_path_before_future_authority() -> None:
    payload = _payload()
    payload["fixture_catalog"]["executable_artifact_path"] = "fixtures/quantum/identity.json"

    errors = validate_payload(payload)

    assert "fixture_catalog.executable_artifact_path must be null" in errors
    assert payload["fixture_catalog"]["executable_artifact_path"].endswith(".json")
    assert payload["fixture_catalog"]["requires_future_fixture_schema"] is True


def test_rejects_missing_related_boundary_witness() -> None:
    payload = _payload()
    payload["related_witness_refs"] = ["non_live_openqasm_export_planning_witness"]

    errors = validate_payload(payload)

    assert any("non_live_local_quantum_simulator_boundary_witness" in error for error in errors)
    assert "non_live_local_quantum_simulator_boundary_witness" not in payload["related_witness_refs"]
    assert payload["openqasm_planning_witness_required"] is True

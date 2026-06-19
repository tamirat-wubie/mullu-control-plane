from __future__ import annotations

import json
import pathlib

from scripts.validate_non_live_local_quantum_simulator_boundary_witness import validate_payload

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "non_live_local_quantum_simulator_boundary_witness.foundation.json"


def _payload() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_non_live_local_quantum_simulator_boundary_witness_example_is_valid() -> None:
    payload = _payload()

    errors = validate_payload(payload)

    assert errors == []
    assert payload["planning_only"] is True
    assert payload["effect_boundary"]["simulator_runtime_invoked"] is False


def test_rejects_simulator_engine_selection() -> None:
    payload = _payload()
    payload["simulator_boundary"]["engine_selected"] = True

    errors = validate_payload(payload)

    assert "simulator_boundary.engine_selected must be false" in errors
    assert payload["simulator_boundary"]["engine_selected"] is True
    assert payload["effect_boundary"]["simulator_engine_selected"] is False


def test_rejects_simulator_runtime_invocation_effect() -> None:
    payload = _payload()
    payload["effect_boundary"]["simulator_runtime_invoked"] = True

    errors = validate_payload(payload)

    assert "effect_boundary.simulator_runtime_invoked must be false" in errors
    assert payload["effect_boundary"]["simulator_runtime_invoked"] is True
    assert payload["denied_authorities"]["simulator_runtime_invocation_enabled"] is False


def test_rejects_state_vector_materialization_effect() -> None:
    payload = _payload()
    payload["effect_boundary"]["state_vector_materialized"] = True

    errors = validate_payload(payload)

    assert "effect_boundary.state_vector_materialized must be false" in errors
    assert payload["effect_boundary"]["state_vector_materialized"] is True
    assert payload["simulator_boundary"]["state_vector_materialization_allowed"] is False


def test_rejects_measurement_shot_execution() -> None:
    payload = _payload()
    payload["effect_boundary"]["measurement_shots_executed"] = True

    errors = validate_payload(payload)

    assert "effect_boundary.measurement_shots_executed must be false" in errors
    assert payload["effect_boundary"]["measurement_shots_executed"] is True
    assert payload["denied_authorities"]["shot_execution_enabled"] is False


def test_rejects_measurement_histogram_emission() -> None:
    payload = _payload()
    payload["effect_boundary"]["measurement_histogram_emitted"] = True

    errors = validate_payload(payload)

    assert "effect_boundary.measurement_histogram_emitted must be false" in errors
    assert payload["effect_boundary"]["measurement_histogram_emitted"] is True
    assert payload["denied_authorities"]["measurement_histogram_emission_enabled"] is False


def test_rejects_missing_no_runtime_execution_gate() -> None:
    payload = _payload()
    payload["required_boundary_gates"] = [
        gate for gate in payload["required_boundary_gates"] if gate != "NoRuntimeExecutionGate"
    ]

    errors = validate_payload(payload)

    assert any("NoRuntimeExecutionGate" in error for error in errors)
    assert "NoRuntimeExecutionGate" not in payload["required_boundary_gates"]
    assert len(payload["required_boundary_gates"]) == 10


def test_rejects_engine_name_before_future_witness() -> None:
    payload = _payload()
    payload["simulator_boundary"]["engine_name"] = "toy-state-vector"

    errors = validate_payload(payload)

    assert "simulator_boundary.engine_name must be null" in errors
    assert payload["simulator_boundary"]["engine_name"] == "toy-state-vector"
    assert payload["simulator_boundary"]["requires_future_simulator_witness"] is True


def test_rejects_allowed_and_denied_output_overlap() -> None:
    payload = _payload()
    payload["allowed_planning_outputs"].append("measurement_histogram")

    errors = validate_payload(payload)

    assert any("allowed planning outputs overlap denied outputs" in error for error in errors)
    assert "measurement_histogram" in payload["allowed_planning_outputs"]
    assert "measurement_histogram" in payload["denied_outputs"]

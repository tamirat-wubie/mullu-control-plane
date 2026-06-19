from __future__ import annotations

import json
import pathlib

from scripts.validate_non_live_openqasm_export_planning_witness import validate_payload

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "non_live_openqasm_export_planning_witness.foundation.json"


def _payload() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_non_live_openqasm_export_planning_witness_example_is_valid() -> None:
    payload = _payload()

    errors = validate_payload(payload)

    assert errors == []
    assert payload["planning_only"] is True
    assert payload["effect_boundary"]["openqasm_file_written"] is False


def test_rejects_openqasm_source_text_emission() -> None:
    payload = _payload()
    payload["effect_boundary"]["openqasm_source_text_emitted"] = True

    errors = validate_payload(payload)

    assert "effect_boundary.openqasm_source_text_emitted must be false" in errors
    assert payload["effect_boundary"]["openqasm_source_text_emitted"] is True
    assert payload["effect_boundary"]["backend_called"] is False


def test_rejects_openqasm_file_write_effect() -> None:
    payload = _payload()
    payload["effect_boundary"]["openqasm_file_written"] = True

    errors = validate_payload(payload)

    assert "effect_boundary.openqasm_file_written must be false" in errors
    assert payload["effect_boundary"]["openqasm_file_written"] is True
    assert payload["denied_authorities"]["openqasm_source_emission_enabled"] is False


def test_rejects_simulator_runtime_execution_authority() -> None:
    payload = _payload()
    payload["denied_authorities"]["simulator_runtime_execution_enabled"] = True

    errors = validate_payload(payload)

    assert "denied_authorities.simulator_runtime_execution_enabled must be false" in errors
    assert payload["denied_authorities"]["simulator_runtime_execution_enabled"] is True
    assert payload["effect_boundary"]["simulator_invoked"] is False


def test_rejects_backend_call_effect() -> None:
    payload = _payload()
    payload["effect_boundary"]["backend_called"] = True

    errors = validate_payload(payload)

    assert "effect_boundary.backend_called must be false" in errors
    assert payload["effect_boundary"]["backend_called"] is True
    assert payload["denied_authorities"]["backend_execution_enabled"] is False


def test_rejects_missing_no_execution_gate() -> None:
    payload = _payload()
    payload["required_planning_gates"] = [
        gate for gate in payload["required_planning_gates"] if gate != "NoExecutionAuthorityGate"
    ]

    errors = validate_payload(payload)

    assert any("NoExecutionAuthorityGate" in error for error in errors)
    assert "NoExecutionAuthorityGate" not in payload["required_planning_gates"]
    assert len(payload["required_planning_gates"]) == 9


def test_rejects_allowed_and_denied_output_overlap() -> None:
    payload = _payload()
    payload["allowed_planning_outputs"].append("openqasm_source_file")

    errors = validate_payload(payload)

    assert any("allowed planning outputs overlap denied outputs" in error for error in errors)
    assert "openqasm_source_file" in payload["allowed_planning_outputs"]
    assert "openqasm_source_file" in payload["denied_outputs"]


def test_rejects_source_file_path_before_exporter_authority() -> None:
    payload = _payload()
    payload["openqasm_target"]["source_file_path"] = "build/planned_circuit.qasm"

    errors = validate_payload(payload)

    assert "openqasm_target.source_file_path must be null" in errors
    assert payload["openqasm_target"]["source_file_path"].endswith(".qasm")
    assert payload["openqasm_target"]["requires_future_exporter_witness"] is True

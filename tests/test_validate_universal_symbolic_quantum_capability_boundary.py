from __future__ import annotations

import json
import pathlib

from scripts.validate_universal_symbolic_quantum_capability_boundary import validate_payload

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "universal_symbolic_quantum_capability_boundary.foundation.json"


def _payload() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_universal_symbolic_quantum_capability_boundary_example_is_valid() -> None:
    assert validate_payload(_payload()) == []


def test_rejects_live_qpu_execution_authority() -> None:
    payload = _payload()
    payload["denied_authorities"]["live_qpu_execution_enabled"] = True

    errors = validate_payload(payload)

    assert "denied_authorities.live_qpu_execution_enabled must be false" in errors


def test_rejects_quantum_advantage_overclaim() -> None:
    payload = _payload()
    payload["quantum_advantage_claim_made"] = True

    errors = validate_payload(payload)

    assert "quantum_advantage_claim_made must be false" in errors


def test_rejects_missing_required_gate() -> None:
    payload = _payload()
    payload["required_gates"] = [
        gate for gate in payload["required_gates"] if gate != "ResourceHonestyGate"
    ]

    errors = validate_payload(payload)

    assert any("ResourceHonestyGate" in error for error in errors)


def test_rejects_allowed_and_denied_role_overlap() -> None:
    payload = _payload()
    payload["symbolic_control_plane_role"]["allowed_roles"].append("live_qpu_execution")

    errors = validate_payload(payload)

    assert any("allowed and denied roles overlap" in error for error in errors)


def test_rejects_fault_tolerant_claim_without_evidence() -> None:
    payload = _payload()
    payload["fault_tolerant_claim_made"] = True

    errors = validate_payload(payload)

    assert "fault_tolerant_claim_made must be false" in errors


def test_rejects_secret_serialization_effect() -> None:
    payload = _payload()
    payload["effect_boundary"]["secret_values_serialized"] = True

    errors = validate_payload(payload)

    assert "effect_boundary.secret_values_serialized must be false" in errors

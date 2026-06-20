"""Test the non-live quantum boundary review packet validator.

Purpose: verify review-only closure for the non-live quantum witness stack.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: foundation example JSON and review packet validator.
Invariants: no implementation authority, source emission, runtime invocation,
credential access, result claim, or terminal closure.
"""

from __future__ import annotations

import json
import pathlib

from scripts.validate_non_live_quantum_boundary_review_packet import validate_payload

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "non_live_quantum_boundary_review_packet.foundation.json"


def _payload() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_non_live_quantum_boundary_review_packet_example_is_valid() -> None:
    payload = _payload()

    errors = validate_payload(payload)

    assert errors == []
    assert payload["planning_only"] is True
    assert payload["implementation_allowed"] is False
    assert len(payload["witness_reviews"]) == 5


def test_rejects_openqasm_exporter_implementation_authority() -> None:
    payload = _payload()
    payload["denied_authorities"]["openqasm_exporter_implementation_enabled"] = True

    errors = validate_payload(payload)

    assert "denied_authorities.openqasm_exporter_implementation_enabled must be false" in errors
    assert payload["denied_authorities"]["openqasm_exporter_implementation_enabled"] is True
    assert payload["effect_boundary"]["openqasm_source_emitted"] is False


def test_rejects_runtime_invocation_effect() -> None:
    payload = _payload()
    payload["effect_boundary"]["simulator_runtime_invoked"] = True

    errors = validate_payload(payload)

    assert "effect_boundary.simulator_runtime_invoked must be false" in errors
    assert payload["effect_boundary"]["simulator_runtime_invoked"] is True
    assert payload["review_boundary"]["runtime_execution_allowed"] is False


def test_rejects_review_boundary_output_path() -> None:
    payload = _payload()
    payload["review_boundary"]["output_path"] = "governance/quantum/review-output.json"

    errors = validate_payload(payload)

    assert "review_boundary.output_path must be null" in errors
    assert payload["review_boundary"]["output_path"].endswith(".json")
    assert payload["review_boundary"]["requires_future_implementation_witness"] is True


def test_rejects_child_witness_runtime_authority() -> None:
    payload = _payload()
    payload["witness_reviews"][2]["runtime_authority_granted"] = True

    errors = validate_payload(payload)

    assert "witness_reviews[2].runtime_authority_granted must be false" in errors
    assert payload["witness_reviews"][2]["runtime_authority_granted"] is True
    assert payload["witness_reviews"][2]["required_future_authority"] is True


def test_rejects_duplicate_witness_review_refs() -> None:
    payload = _payload()
    payload["witness_reviews"][4]["witness_ref"] = payload["witness_reviews"][3]["witness_ref"]

    errors = validate_payload(payload)

    assert "witness_reviews.witness_ref values must be unique" in errors
    assert any("non_live_quantum_fixture_serializer_boundary_witness" in error for error in errors)
    assert payload["witness_reviews"][4]["witness_ref"] == payload["witness_reviews"][3]["witness_ref"]


def test_rejects_missing_no_runtime_execution_gate() -> None:
    payload = _payload()
    payload["required_review_gates"] = [
        gate for gate in payload["required_review_gates"] if gate != "NoRuntimeExecutionGate"
    ]

    errors = validate_payload(payload)

    assert any("NoRuntimeExecutionGate" in error for error in errors)
    assert "NoRuntimeExecutionGate" not in payload["required_review_gates"]
    assert len(payload["required_review_gates"]) == 11


def test_rejects_missing_reviewed_witness_ref() -> None:
    payload = _payload()
    payload["reviewed_witness_refs"] = [
        "universal_symbolic_quantum_capability_boundary",
        "non_live_openqasm_export_planning_witness",
    ]

    errors = validate_payload(payload)

    assert any("non_live_local_quantum_simulator_boundary_witness" in error for error in errors)
    assert "non_live_quantum_fixture_catalog_witness" not in payload["reviewed_witness_refs"]
    assert payload["future_separate_pr_required"] is True

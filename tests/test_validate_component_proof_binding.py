"""Tests for Component Harness proof binding validation.

Purpose: prove component proof bindings fail closed against registry, router,
proof matrix, witness, evidence, and authority drift.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_proof_binding and foundation examples.
Invariants:
  - Every registered component is bound exactly once.
  - Receipt claims require proof witnesses.
  - Router inventory proof surfaces cannot drift from component bindings.
  - Proof binding cannot claim terminal closure.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_component_proof_binding import (
    DEFAULT_BINDING,
    DEFAULT_OUTPUT,
    validate_component_proof_binding,
    write_component_proof_binding_validation,
)


def _load_default_binding() -> dict[str, object]:
    return json.loads(DEFAULT_BINDING.read_text(encoding="utf-8"))


def _write_binding(tmp_path: Path, payload: dict[str, object]) -> Path:
    binding_path = tmp_path / "component_proof_binding.json"
    binding_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return binding_path


def _binding_for(payload: dict[str, object], component_id: str) -> dict[str, object]:
    bindings = payload["component_bindings"]
    assert isinstance(bindings, list)
    for component_binding in bindings:
        assert isinstance(component_binding, dict)
        if component_binding.get("component_id") == component_id:
            return component_binding
    raise AssertionError(f"missing component binding {component_id}")


def test_default_component_proof_binding_validates_and_writes_receipt(tmp_path: Path) -> None:
    validation = validate_component_proof_binding()
    output_path = tmp_path / "proof-binding-validation.json"

    written_path = write_component_proof_binding_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.binding_count == 10
    assert validation.proof_bound_count == 9
    assert validation.referenced_surface_count >= 10
    assert written_payload["ok"] is True
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "component_proof_binding_validation.json"


def test_missing_component_binding_fails_closed(tmp_path: Path) -> None:
    payload = _load_default_binding()
    bindings = payload["component_bindings"]
    assert isinstance(bindings, list)
    payload["component_bindings"] = [
        binding for binding in bindings if binding.get("component_id") != "snet"
    ]

    validation = validate_component_proof_binding(binding_path=_write_binding(tmp_path, payload))

    assert validation.ok is False
    assert validation.binding_count == 9
    assert any("registered components missing proof bindings ['snet']" in error for error in validation.errors)


def test_unknown_required_surface_fails_closed(tmp_path: Path) -> None:
    payload = _load_default_binding()
    snet_binding = _binding_for(payload, "snet")
    snet_binding["required_surface_ids"] = ["missing_surface"]

    validation = validate_component_proof_binding(binding_path=_write_binding(tmp_path, payload))

    assert validation.ok is False
    assert validation.referenced_surface_count >= 1
    assert any("required_surface_ids must include registry surface snet_operator_read_model" in error for error in validation.errors)
    assert any("surface missing_surface is not in generated proof matrix" in error for error in validation.errors)


def test_receipt_required_without_runtime_witness_fails_closed(tmp_path: Path) -> None:
    payload = _load_default_binding()
    harness_binding = _binding_for(payload, "agentic_service_harness")
    harness_binding["required_runtime_witnesses"] = []

    validation = validate_component_proof_binding(binding_path=_write_binding(tmp_path, payload))

    assert validation.ok is False
    assert validation.proof_bound_count == 9
    assert any("receipt_required binding must list runtime witnesses" in error for error in validation.errors)


def test_router_inventory_surface_drift_fails_closed(tmp_path: Path) -> None:
    payload = _load_default_binding()
    assistant_binding = _binding_for(payload, "personal_assistant")
    assistant_binding["inventory_surface_ids"] = ["assistant_kernel_planning"]

    validation = validate_component_proof_binding(binding_path=_write_binding(tmp_path, payload))

    assert validation.ok is False
    assert validation.binding_count == 10
    assert any("inventory_surface_ids must match router inventory" in error for error in validation.errors)


def test_evidence_file_not_on_referenced_surface_fails_closed(tmp_path: Path) -> None:
    payload = _load_default_binding()
    worker_binding = _binding_for(payload, "worker_runtime")
    worker_binding["required_evidence_files"] = ["gateway/server.py"]

    validation = validate_component_proof_binding(binding_path=_write_binding(tmp_path, payload))

    assert validation.ok is False
    assert validation.proof_bound_count == 9
    assert any("evidence files are not present on referenced surfaces ['gateway/server.py']" in error for error in validation.errors)


def test_runtime_witness_not_on_referenced_surface_fails_closed(tmp_path: Path) -> None:
    payload = _load_default_binding()
    capability_binding = _binding_for(payload, "capability_workers")
    capability_binding["required_runtime_witnesses"] = ["worker_mesh_schema_valid"]

    validation = validate_component_proof_binding(binding_path=_write_binding(tmp_path, payload))

    assert validation.ok is False
    assert validation.proof_bound_count == 9
    assert any("runtime witnesses are not present on referenced surfaces ['worker_mesh_schema_valid']" in error for error in validation.errors)


def test_terminal_closure_claim_fails_closed(tmp_path: Path) -> None:
    payload = _load_default_binding()
    governance_binding = _binding_for(payload, "governance_core")
    governance_binding["can_claim_terminal_closure"] = True

    validation = validate_component_proof_binding(binding_path=_write_binding(tmp_path, payload))

    assert validation.ok is False
    assert validation.binding_count == 10
    assert any("can_claim_terminal_closure" in error for error in validation.errors)
    assert any("cannot claim terminal closure" in error for error in validation.errors)


def test_awaiting_binding_with_surface_fails_closed(tmp_path: Path) -> None:
    payload = _load_default_binding()
    nested_binding = _binding_for(payload, "nested_mind_bridge")
    nested_binding["required_surface_ids"] = ["operator_console_read_models"]

    validation = validate_component_proof_binding(binding_path=_write_binding(tmp_path, payload))

    assert validation.ok is False
    assert validation.referenced_surface_count >= 1
    assert any("awaiting_binding must not list required_surface_ids" in error for error in validation.errors)


def test_source_reference_drift_fails_closed(tmp_path: Path) -> None:
    payload = _load_default_binding()
    payload["source_proof_matrix"] = "docs/40_proof_coverage_matrix.md"

    validation = validate_component_proof_binding(binding_path=_write_binding(tmp_path, payload))

    assert validation.ok is False
    assert validation.binding_count == 10
    assert any("source_proof_matrix must be 'tests/fixtures/proof_coverage_matrix.json'" in error for error in validation.errors)

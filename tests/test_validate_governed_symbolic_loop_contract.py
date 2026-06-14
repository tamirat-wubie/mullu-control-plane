"""Purpose: verify governed symbolic loop contract validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_governed_symbolic_loop_contract and SDLC validator.
Invariants:
  - The contract remains read-only and non-terminal.
  - Effect-bearing guards reject missing UAO, rollback, and learning gates.
  - SDLC evidence artifacts validate without granting runtime authority.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_governed_symbolic_loop_contract as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_governed_symbolic_loop_contract_passes() -> None:
    errors = validator.validate_contract()
    contract = validator.load_json_object(
        validator.DEFAULT_CONTRACT_PATH,
        "governed symbolic loop contract",
    )

    assert errors == []
    assert contract["surface"] == validator.EXPECTED_SURFACE
    assert tuple(contract["canonical_phases"]) == validator.EXPECTED_PHASES
    assert tuple(contract["action_classes"]) == validator.EXPECTED_ACTION_CLASSES
    assert contract["solver_outcome"] == "AwaitingEvidence"
    assert contract["non_runtime_guards"]["read_only"] is True
    assert contract["non_runtime_guards"]["read_model_registry_admission_claimed"] is True
    assert contract["non_runtime_guards"]["runtime_registration_claimed"] is False
    assert contract["non_runtime_guards"]["execution_authority_granted"] is False
    assert contract["non_runtime_guards"]["connector_authority_granted"] is False
    assert contract["non_runtime_guards"]["deployment_claimed"] is False
    assert contract["non_runtime_guards"]["terminal_closure"] is False
    assert contract["effect_bearing_guards"]["learning_after_verification_only"] is True
    assert validator.validate_contract_record(contract) == []


def test_contract_rejects_runtime_authority_and_learning_mutations() -> None:
    mutated = validator.build_mutated_contract(
        non_runtime_guards__read_model_registry_admission_claimed=False,
        non_runtime_guards__runtime_registration_claimed=True,
        non_runtime_guards__execution_authority_granted=True,
        non_runtime_guards__connector_authority_granted=True,
        non_runtime_guards__deployment_claimed=True,
        non_runtime_guards__terminal_closure=True,
        effect_bearing_guards__learning_after_verification_only=False,
    )

    errors = validator.validate_contract_record(mutated)

    assert any("read_model_registry_admission_claimed" in error for error in errors)
    assert any("runtime_registration_claimed" in error for error in errors)
    assert any("execution_authority_granted" in error for error in errors)
    assert any("connector_authority_granted" in error for error in errors)
    assert any("deployment_claimed" in error for error in errors)
    assert any("terminal_closure" in error for error in errors)
    assert any("learning_after_verification_only" in error for error in errors)
    assert mutated["non_runtime_guards"]["read_only"] is True
    assert mutated["effect_bearing_guards"]["uao_required"] is True


def test_contract_rejects_receipt_prefix_and_evidence_drift() -> None:
    mutated = validator.build_mutated_contract(
        receipt_envelope__uao_ref="trace://wrong/platform/loop",
        receipt_envelope__causal_decision_trace_ref="receipt://wrong/platform/loop",
        receipt_envelope__receipt_ref="uao://wrong/platform/loop",
    )
    mutated["evidence_refs"] = [
        ref
        for ref in mutated["evidence_refs"]
        if ref != "tests/test_validate_governed_symbolic_loop_contract.py"
    ]
    mutated["required_evidence"] = [
        ref
        for ref in mutated["required_evidence"]
        if ref != "rollback_or_recovery_handoff_receipt"
    ]

    errors = validator.validate_contract_record(mutated)

    assert any("receipt_envelope.uao_ref" in error for error in errors)
    assert any("receipt_envelope.causal_decision_trace_ref" in error for error in errors)
    assert any("receipt_envelope.receipt_ref" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)
    assert any("required_evidence missing required ref" in error for error in errors)
    assert mutated["non_runtime_guards"]["terminal_closure"] is False


def test_contract_rejects_phase_or_action_class_reordering() -> None:
    mutated = validator.build_mutated_contract()
    mutated["canonical_phases"] = list(reversed(mutated["canonical_phases"]))
    mutated["action_classes"] = ["hybrid", "epistemic", "effect_bearing"]

    errors = validator.validate_contract_record(mutated)

    assert any("canonical_phases" in error for error in errors)
    assert any("action_classes" in error for error in errors)
    assert set(mutated["canonical_phases"]) == set(validator.EXPECTED_PHASES)
    assert set(mutated["action_classes"]) == set(validator.EXPECTED_ACTION_CLASSES)


def test_saved_contract_file_validation(tmp_path) -> None:
    contract_path = tmp_path / "governed_symbolic_loop_contract.json"
    contract = validator.load_json_object(
        validator.DEFAULT_CONTRACT_PATH,
        "governed symbolic loop contract",
    )
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    loaded = validator.load_json_object(contract_path, "saved governed symbolic loop contract")
    errors = validator.validate_contract_record(loaded)

    assert errors == []
    assert loaded["contract_id"] == "governed_symbolic_loop_contract_foundation_20260614"
    assert loaded["receipt_envelope"]["uao_ref"].startswith("uao://")
    assert loaded["receipt_envelope"]["causal_decision_trace_ref"].startswith("trace://")
    assert loaded["receipt_envelope"]["receipt_ref"].startswith("receipt://")


def test_malformed_contract_payload_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_contract_record(None, schema)
    list_errors = validator.validate_contract_record([], schema)

    assert any("contract must be a JSON object" in error for error in none_errors)
    assert any("contract must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_governed_symbolic_loop() -> None:
    requirement_path = Path("examples/sdlc/requirement_governed_symbolic_loop_20260614.json")
    design_path = Path("examples/sdlc/design_governed_symbolic_loop_20260614.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "governed symbolic loop requirement")
    design = sdlc_validator.load_json_object(design_path, "governed symbolic loop design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/governed_symbolic_loop_contract.schema.json" in design["schema_changes"]
    assert "scripts/validate_governed_symbolic_loop_contract.py" in design["validator_changes"]
    assert "no runtime loop registration" in requirement["non_goals"]
    assert "read-only holistic loop registry admission is allowed and must not grant runtime registration" in requirement["success_criteria"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True
    assert any("run_workspace_governance_checks.py" in command for command in design["test_plan"])

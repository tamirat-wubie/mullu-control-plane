"""Purpose: verify ProblemStar compilation receipt validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_problem_star_compilation_receipt and SDLC validator.
Invariants:
  - ProblemStar field order preserves the Phi-GPS v2.2 kernel object.
  - Compilation evidence is separated before solver routing.
  - Runtime, connector, deployment, and terminal closure authority remain denied.
  - The SDLC requirement and design artifacts validate.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_problem_star_compilation_receipt as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_problem_star_compilation_receipt_passes() -> None:
    errors = validator.validate_receipt()
    receipt = validator.load_json_object(validator.DEFAULT_RECEIPT_PATH, "ProblemStar compilation receipt")

    assert errors == []
    assert receipt["receipt_version"] == validator.EXPECTED_RECEIPT_VERSION
    assert receipt["compiler_name"] == validator.EXPECTED_COMPILER_NAME
    assert receipt["schema_version"] == validator.EXPECTED_SCHEMA_VERSION
    assert receipt["kernel_schema_version"] == validator.EXPECTED_KERNEL_SCHEMA_VERSION
    assert tuple(receipt["kernel_draft"]["field_order"]) == validator.EXPECTED_FIELD_ORDER
    assert tuple(receipt["kernel_draft"]["fields"].keys()) == validator.EXPECTED_FIELD_ORDER
    assert receipt["compilation_outcome"] == "SolvedVerified"
    assert validator.validate_receipt_record(receipt) == []


def test_receipt_rejects_runtime_authority_and_terminal_claims() -> None:
    mutated = validator.build_mutated_receipt(
        governance_guards__runtime_registration_claimed=True,
        governance_guards__execution_authority_granted=True,
        governance_guards__connector_authority_granted=True,
        governance_guards__deployment_claimed=True,
        governance_guards__terminal_closure=True,
    )

    errors = validator.validate_receipt_record(mutated)

    assert any("runtime_registration_claimed" in error for error in errors)
    assert any("execution_authority_granted" in error for error in errors)
    assert any("connector_authority_granted" in error for error in errors)
    assert any("deployment_claimed" in error for error in errors)
    assert any("terminal_closure" in error for error in errors)
    assert mutated["governance_guards"]["mfidel_atomicity_preserved"] is True


def test_receipt_rejects_problem_star_field_order_drift() -> None:
    mutated = validator.build_mutated_receipt()
    mutated["kernel_draft"]["field_order"] = list(reversed(mutated["kernel_draft"]["field_order"]))
    mutated["kernel_draft"]["fields"] = {
        key: mutated["kernel_draft"]["fields"][key]
        for key in reversed(list(mutated["kernel_draft"]["fields"].keys()))
    }

    errors = validator.validate_receipt_record(mutated)

    assert any("field_order" in error for error in errors)
    assert any("fields must preserve" in error for error in errors)
    assert set(mutated["kernel_draft"]["field_order"]) == set(validator.EXPECTED_FIELD_ORDER)
    assert set(mutated["kernel_draft"]["fields"].keys()) == set(validator.EXPECTED_FIELD_ORDER)


def test_receipt_rejects_merged_evidence_assumption_and_missing_proof() -> None:
    mutated = validator.build_mutated_receipt()
    mutated["separated_surfaces"]["assumptions"] = mutated["separated_surfaces"]["evidence"]
    mutated["separated_surfaces"]["proof_obligations"] = []
    mutated["governance_guards"]["evidence_assumption_separated"] = False
    mutated["governance_guards"]["contradictions_append_only"] = False

    errors = validator.validate_receipt_record(mutated)

    assert any("evidence and assumptions must remain distinct" in error for error in errors)
    assert any("proof_obligations must not be empty" in error for error in errors)
    assert any("evidence_assumption_separated" in error for error in errors)
    assert any("contradictions_append_only" in error for error in errors)
    assert mutated["separated_surfaces"]["available_actions"]


def test_receipt_rejects_bad_receipt_prefix_and_evidence_drift() -> None:
    mutated = validator.build_mutated_receipt(
        receipt_envelope__uao_ref="trace://wrong/problem-star",
        receipt_envelope__causal_decision_trace_ref="receipt://wrong/problem-star",
        receipt_envelope__receipt_ref="uao://wrong/problem-star",
    )
    mutated["evidence_refs"] = [
        ref
        for ref in mutated["evidence_refs"]
        if ref != "tests/test_validate_problem_star_compilation_receipt.py"
    ]

    errors = validator.validate_receipt_record(mutated)

    assert any("receipt_envelope.uao_ref" in error for error in errors)
    assert any("receipt_envelope.causal_decision_trace_ref" in error for error in errors)
    assert any("receipt_envelope.receipt_ref" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)
    assert mutated["governance_guards"]["runtime_registration_claimed"] is False


def test_saved_receipt_file_validation(tmp_path: Path) -> None:
    receipt_path = tmp_path / "problem_star_compilation_receipt.json"
    receipt = validator.load_json_object(validator.DEFAULT_RECEIPT_PATH, "ProblemStar compilation receipt")
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    loaded = validator.load_json_object(receipt_path, "saved ProblemStar compilation receipt")
    errors = validator.validate_receipt_record(loaded)

    assert errors == []
    assert loaded["receipt_id"] == "problem_star_compilation_receipt_foundation_20260614"
    assert loaded["receipt_envelope"]["uao_ref"].startswith("uao://")
    assert loaded["receipt_envelope"]["causal_decision_trace_ref"].startswith("trace://")
    assert loaded["receipt_envelope"]["receipt_ref"].startswith("receipt://")


def test_malformed_receipt_payload_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_receipt_record(None, schema)
    list_errors = validator.validate_receipt_record([], schema)

    assert any("receipt must be a JSON object" in error for error in none_errors)
    assert any("receipt must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_problem_star_receipt() -> None:
    requirement_path = Path("examples/sdlc/requirement_problem_star_compilation_receipt_20260614.json")
    design_path = Path("examples/sdlc/design_problem_star_compilation_receipt_20260614.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "ProblemStar receipt requirement")
    design = sdlc_validator.load_json_object(design_path, "ProblemStar receipt design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/problem_star_compilation_receipt.schema.json" in design["schema_changes"]
    assert "scripts/validate_problem_star_compilation_receipt.py" in design["validator_changes"]
    assert "no runtime solver registration" in requirement["non_goals"]
    assert "the receipt denies runtime, connector, deployment, and terminal closure authority" in requirement["success_criteria"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True
    assert any("run_workspace_governance_checks.py" in command for command in design["test_plan"])

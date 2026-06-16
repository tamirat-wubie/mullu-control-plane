"""Purpose: verify MfidelSubstrateConformanceReceipt validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_mfidel_substrate_conformance_receipt and SDLC validator.
Invariants:
  - Mfidel symbols remain atomic and exact-preserved.
  - Unicode normalization and decomposition remain denied.
  - Cross-runtime SDK/kernel bindings remain AwaitingEvidence until witnessed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_mfidel_substrate_conformance_receipt as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_mfidel_substrate_conformance_receipt_passes() -> None:
    errors = validator.validate_mfidel_substrate_conformance_receipt()
    receipt = validator.load_json_object(
        validator.DEFAULT_RECEIPT_PATH,
        "MfidelSubstrateConformanceReceipt",
    )

    assert errors == []
    assert receipt["receipt_version"] == validator.EXPECTED_RECEIPT_VERSION
    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["substrate_scope"]["grid_rows"] == 34
    assert receipt["substrate_scope"]["grid_cols"] == 8
    assert receipt["substrate_scope"]["vector_dimension"] == 272
    assert receipt["substrate_scope"]["cross_runtime_closure_claimed"] is False
    assert receipt["contract_summary"]["validated_binding_count"] == 3
    assert receipt["contract_summary"]["awaiting_evidence_binding_count"] == 3
    assert validator.validate_mfidel_substrate_conformance_receipt_record(receipt) == []


def test_mfidel_substrate_conformance_receipt_rejects_atomicity_guard_drift() -> None:
    mutated = validator.build_mutated_mfidel_substrate_conformance_receipt(
        atomicity_guards__unicode_normalization_allowed=True,
        atomicity_guards__unicode_decomposition_allowed=True,
        atomicity_guards__unicode_recomposition_allowed=True,
        atomicity_guards__root_letter_model_allowed=True,
        atomicity_guards__consonant_vowel_split_allowed=True,
        atomicity_guards__overlay_structural_decomposition_allowed=True,
        atomicity_guards__terminal_closure_allowed=True,
    )

    errors = validator.validate_mfidel_substrate_conformance_receipt_record(mutated)

    assert any("unicode_normalization_allowed" in error for error in errors)
    assert any("unicode_decomposition_allowed" in error for error in errors)
    assert any("unicode_recomposition_allowed" in error for error in errors)
    assert any("root_letter_model_allowed" in error for error in errors)
    assert any("consonant_vowel_split_allowed" in error for error in errors)
    assert any("overlay_structural_decomposition_allowed" in error for error in errors)
    assert any("terminal_closure_allowed" in error for error in errors)


def test_mfidel_substrate_conformance_receipt_rejects_digest_drift() -> None:
    mutated = validator.build_mutated_mfidel_substrate_conformance_receipt(
        runtime_bindings__0__digest_sha256="0" * 64,
        runtime_bindings__0__no_normalization_proof_refs=[],
        runtime_bindings__0__exact_preservation_proof_refs=[],
        runtime_bindings__0__gap_refs=["gap://unexpected/local-gap"],
    )

    errors = validator.validate_mfidel_substrate_conformance_receipt_record(mutated)

    assert any("digest_sha256 does not match" in error for error in errors)
    assert any("no_normalization_proof_refs required" in error for error in errors)
    assert any("exact_preservation_proof_refs required" in error for error in errors)
    assert any("gap_refs must be empty" in error for error in errors)


def test_mfidel_substrate_conformance_receipt_rejects_exact_preservation_drift() -> None:
    mutated = validator.build_mutated_mfidel_substrate_conformance_receipt(
        exact_preservation_witnesses__0__codepoints=["U+1208", "U+1200"],
        exact_preservation_witnesses__0__expected_positions=[
            {"row": 2, "col": 1},
            {"row": 1, "col": 1},
        ],
        exact_preservation_witnesses__0__normalization_applied=True,
    )

    errors = validator.validate_mfidel_substrate_conformance_receipt_record(mutated)

    assert any("codepoints must match input_sequence" in error for error in errors)
    assert any("expected_positions must match runtime lookup" in error for error in errors)
    assert any("normalization_applied must be false" in error for error in errors)


def test_mfidel_substrate_conformance_receipt_rejects_decomposed_like_input() -> None:
    mutated = validator.build_mutated_mfidel_substrate_conformance_receipt(
        exact_preservation_witnesses__0__input_sequence="\u1200\u0301",
        exact_preservation_witnesses__0__codepoints=["U+1200", "U+0301"],
        exact_preservation_witnesses__0__expected_positions=[{"row": 1, "col": 1}],
    )

    errors = validator.validate_mfidel_substrate_conformance_receipt_record(mutated)

    assert any("input_sequence rejected" in error for error in errors)
    assert any("non-fidel characters" in error for error in errors)
    assert any("one fidel per input symbol" not in error for error in errors) or errors


def test_mfidel_substrate_conformance_receipt_rejects_cross_runtime_gap_drift() -> None:
    mutated = validator.build_mutated_mfidel_substrate_conformance_receipt(
        solver_outcome="SolvedUnverified",
        substrate_scope__cross_runtime_closure_claimed=True,
        runtime_bindings__3__conformance_status="validated",
        runtime_bindings__3__digest_sha256="1" * 64,
        runtime_bindings__3__no_normalization_proof_refs=["test://unexpected"],
        runtime_bindings__3__exact_preservation_proof_refs=["test://unexpected"],
        runtime_bindings__3__gap_refs=[],
    )

    errors = validator.validate_mfidel_substrate_conformance_receipt_record(mutated)

    assert any("cross_runtime_closure_claimed" in error for error in errors)
    assert any("conformance_status must be awaiting_evidence" in error for error in errors)
    assert any("digest_sha256 must be null" in error for error in errors)
    assert any("no_normalization_proof_refs must be empty" in error for error in errors)
    assert any("exact_preservation_proof_refs must be empty" in error for error in errors)
    assert any("gap_refs required" in error for error in errors)
    assert any("solver_outcome must remain AwaitingEvidence" in error for error in errors)


def test_mfidel_substrate_conformance_receipt_rejects_summary_drift() -> None:
    mutated = validator.build_mutated_mfidel_substrate_conformance_receipt(
        contract_summary__runtime_binding_count=1,
        contract_summary__validated_binding_count=1,
        contract_summary__awaiting_evidence_binding_count=1,
        contract_summary__exact_preservation_witness_count=1,
        contract_summary__evidence_ref_count=1,
    )

    errors = validator.validate_mfidel_substrate_conformance_receipt_record(mutated)

    assert any("runtime_binding_count" in error for error in errors)
    assert any("validated_binding_count" in error for error in errors)
    assert any("awaiting_evidence_binding_count" in error for error in errors)
    assert any("exact_preservation_witness_count" in error for error in errors)
    assert any("evidence_ref_count" in error for error in errors)


def test_mfidel_substrate_conformance_receipt_rejects_missing_refs() -> None:
    mutated = validator.build_mutated_mfidel_substrate_conformance_receipt(
        receipt_refs__mfidel_grid_runtime="mcoi/mcoi_runtime/substrate/mfidel/other.py",
        evidence_refs=["schemas/mfidel_substrate_conformance_receipt.schema.json"],
    )

    errors = validator.validate_mfidel_substrate_conformance_receipt_record(mutated)

    assert any("receipt_refs.mfidel_grid_runtime" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)
    assert len(errors) >= 2


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/mfidel_substrate_conformance_receipt.schema.json",
            "--receipt",
            "examples/mfidel_substrate_conformance_receipt.foundation.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["schema_path"]).as_posix() == "schemas/mfidel_substrate_conformance_receipt.schema.json"
    assert Path(payload["receipt_path"]).as_posix() == "examples/mfidel_substrate_conformance_receipt.foundation.json"
    assert payload["errors"] == []


def test_malformed_mfidel_substrate_conformance_receipt_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_mfidel_substrate_conformance_receipt_record(None, schema)
    list_errors = validator.validate_mfidel_substrate_conformance_receipt_record([], schema)

    assert any("mfidel substrate conformance receipt must be a JSON object" in error for error in none_errors)
    assert any("mfidel substrate conformance receipt must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_mfidel_substrate_conformance_receipt() -> None:
    requirement_path = Path("examples/sdlc/requirement_mfidel_substrate_conformance_receipt_20260616.json")
    design_path = Path("examples/sdlc/design_mfidel_substrate_conformance_receipt_20260616.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "mfidel substrate requirement")
    design = sdlc_validator.load_json_object(design_path, "mfidel substrate design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/mfidel_substrate_conformance_receipt.schema.json" in requirement["affected_surfaces"]
    assert "schemas/mfidel_substrate_conformance_receipt.schema.json" in design["schema_changes"]
    assert "scripts/validate_mfidel_substrate_conformance_receipt.py" in design["validator_changes"]
    assert "tests/test_validate_mfidel_substrate_conformance_receipt.py" in design["validator_changes"]
    assert "no Unicode normalization" in requirement["non_goals"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True

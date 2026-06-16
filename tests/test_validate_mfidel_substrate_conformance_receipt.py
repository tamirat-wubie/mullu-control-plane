"""Purpose: verify MfidelSubstrateConformanceReceipt validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_mfidel_substrate_conformance_receipt and SDLC validator.
Invariants:
  - Fidel sequences are preserved exactly.
  - Unicode normalization and decomposition paths are rejected.
  - Cross-runtime parity remains AwaitingEvidence until fixtures are bound.
  - The SDLC requirement, design, and security review artifacts validate.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_mfidel_substrate_conformance_receipt as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_mfidel_substrate_conformance_receipt_passes() -> None:
    errors = validator.validate_mfidel_substrate_conformance_receipt()
    receipt = validator.load_json_object(validator.DEFAULT_RECEIPT_PATH, "MfidelSubstrateConformanceReceipt")

    assert errors == []
    assert receipt["receipt_version"] == validator.EXPECTED_RECEIPT_VERSION
    assert receipt["grid_bounds"]["row_min"] == 1
    assert receipt["grid_bounds"]["row_max"] == 34
    assert receipt["grid_bounds"]["col_max"] == 8
    assert receipt["grid_bounds"]["vibratory_overlay_row"] == 17
    assert receipt["contract_summary"]["runtime_parity_verified"] is False
    assert receipt["cross_runtime_fixture_refs"]["parity_status"] == "AWAITING_RUNTIME_EVIDENCE"
    assert validator.validate_mfidel_substrate_conformance_receipt_record(receipt) == []


def test_mfidel_substrate_conformance_receipt_rejects_normalization_and_decomposition_drift() -> None:
    mutated = validator.build_mutated_mfidel_substrate_conformance_receipt(
        normalization_guards__unicode_normalization_applied=True,
        normalization_guards__unicode_decomposition_performed=True,
        normalization_guards__unicode_recomposition_performed=True,
        normalization_guards__shape_decomposition_performed=True,
        normalization_guards__sound_decomposition_performed=True,
        normalization_guards__internal_letter_model_used=True,
        normalization_guards__sound_overlay_split_performed=True,
        normalization_guards__lossy_transliteration_canonical_store=True,
        normalization_guards__tokenizer_splits_fidel=True,
    )

    errors = validator.validate_mfidel_substrate_conformance_receipt_record(mutated)

    assert any("unicode_normalization_applied" in error for error in errors)
    assert any("unicode_decomposition_performed" in error for error in errors)
    assert any("unicode_recomposition_performed" in error for error in errors)
    assert any("shape_decomposition_performed" in error for error in errors)
    assert any("sound_decomposition_performed" in error for error in errors)
    assert any("internal_letter_model_used" in error for error in errors)
    assert any("sound_overlay_split_performed" in error for error in errors)
    assert any("lossy_transliteration_canonical_store" in error for error in errors)
    assert any("tokenizer_splits_fidel" in error for error in errors)


def test_mfidel_substrate_conformance_receipt_rejects_grid_bound_drift() -> None:
    mutated = validator.build_mutated_mfidel_substrate_conformance_receipt(
        grid_bounds__row_min=0,
        grid_bounds__row_max=35,
        grid_bounds__col_min=0,
        grid_bounds__col_max=9,
        grid_bounds__vibratory_overlay_row=16,
        grid_bounds__overlay_metadata_only=False,
    )
    mutated["atomic_sequence_fixtures"][0]["grid_refs"][0] = "f[99][1]"

    errors = validator.validate_mfidel_substrate_conformance_receipt_record(mutated)

    assert any("grid_bounds.row_min" in error for error in errors)
    assert any("grid_bounds.row_max" in error for error in errors)
    assert any("grid_bounds.col_min" in error for error in errors)
    assert any("grid_bounds.col_max" in error for error in errors)
    assert any("vibratory_overlay_row" in error for error in errors)
    assert any("overlay_metadata_only" in error for error in errors)
    assert any("out-of-bounds ref" in error or "invalid ref" in error for error in errors)


def test_mfidel_substrate_conformance_receipt_rejects_sequence_preservation_drift() -> None:
    mutated = validator.build_mutated_mfidel_substrate_conformance_receipt()
    mutated["atomic_sequence_fixtures"][1]["preserved_sequence"] = "ኧኡኢኣኤእኦ"
    mutated["atomic_sequence_fixtures"][1]["exact_sequence_preserved"] = False
    mutated["atomic_sequence_fixtures"][1]["grid_refs"] = mutated["atomic_sequence_fixtures"][1]["grid_refs"][:-1]
    mutated["atomic_sequence_fixtures"][2]["overlay_semantics"] = "shape_overlay"

    errors = validator.validate_mfidel_substrate_conformance_receipt_record(mutated)

    assert any("preserve fidel_sequence exactly" in error for error in errors)
    assert any("exact_sequence_preserved" in error for error in errors)
    assert any("grid_refs must match fidel sequence length" in error for error in errors)
    assert any("overlay_semantics" in error for error in errors)
    assert mutated["atomic_sequence_fixtures"][1]["fidel_sequence"] == "ኧኡኢኣኤእኦአ"


def test_mfidel_substrate_conformance_receipt_rejects_missing_refs_and_count_drift() -> None:
    mutated = validator.build_mutated_mfidel_substrate_conformance_receipt(
        source_family_refs__live_source_reads_performed=True,
        cross_runtime_fixture_refs__parity_status="PARITY_VERIFIED",
        cross_runtime_fixture_refs__parity_blocked_reason_refs=["blocked://mfidel/python-runtime-fixture-not-bound"],
        receipt_refs__validator="scripts/other_validator.py",
        contract_summary__fixture_count=1,
        contract_summary__receipt_ref_count=1,
        contract_summary__evidence_ref_count=99,
        contract_summary__live_source_reads_performed=True,
        contract_summary__runtime_parity_verified=True,
        contract_summary__terminal_closure_allowed=True,
        evidence_refs=["schemas/mfidel_substrate_conformance_receipt.schema.json"],
    )

    errors = validator.validate_mfidel_substrate_conformance_receipt_record(mutated)

    assert any("live_source_reads_performed" in error for error in errors)
    assert any("parity_status" in error for error in errors)
    assert any("parity_blocked_reason_refs missing required ref" in error for error in errors)
    assert any("receipt_refs.validator" in error for error in errors)
    assert any("contract_summary.fixture_count" in error for error in errors)
    assert any("contract_summary.evidence_ref_count" in error for error in errors)
    assert any("runtime_parity_verified" in error for error in errors)
    assert any("terminal_closure_allowed" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)


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

    assert any("Mfidel substrate conformance receipt must be a JSON object" in error for error in none_errors)
    assert any("Mfidel substrate conformance receipt must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_validator_does_not_call_unicode_normalization() -> None:
    source = Path("scripts/validate_mfidel_substrate_conformance_receipt.py").read_text(encoding="utf-8")
    receipt = validator.load_json_object(validator.DEFAULT_RECEIPT_PATH, "MfidelSubstrateConformanceReceipt")

    assert "unicodedata.normalize" not in source
    assert "normalize(" not in source
    assert receipt["atomic_sequence_fixtures"][0]["fidel_sequence"] == receipt["atomic_sequence_fixtures"][0]["preserved_sequence"]
    assert receipt["normalization_guards"]["unicode_normalization_applied"] is False


def test_sdlc_requirement_design_and_security_validate_for_mfidel_substrate_conformance_receipt() -> None:
    requirement_path = Path("examples/sdlc/requirement_mfidel_substrate_conformance_receipt_20260616.json")
    design_path = Path("examples/sdlc/design_mfidel_substrate_conformance_receipt_20260616.json")
    security_path = Path("examples/sdlc/security_review_mfidel_substrate_conformance_receipt_20260616.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "Mfidel substrate requirement")
    design = sdlc_validator.load_json_object(design_path, "Mfidel substrate design")
    security = sdlc_validator.load_json_object(security_path, "Mfidel substrate security review")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)
    security_errors = sdlc_validator.validate_artifact_record("security_review", security)

    assert requirement_errors == []
    assert design_errors == []
    assert security_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "MfidelSubstrateConformanceReceipt" in design["architecture_summary"]
    assert "schemas/mfidel_substrate_conformance_receipt.schema.json" in requirement["affected_surfaces"]
    assert "schemas/mfidel_substrate_conformance_receipt.schema.json" in design["schema_changes"]
    assert "scripts/validate_mfidel_substrate_conformance_receipt.py" in design["validator_changes"]
    assert "no Unicode normalization" in requirement["non_goals"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True
    assert security["residual_risk"] == "low"

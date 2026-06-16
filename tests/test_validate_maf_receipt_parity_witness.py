"""Purpose: verify MafReceiptParityWitness validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_maf_receipt_parity_witness and SDLC validator.
Invariants:
  - MAF receipt parity remains Foundation Mode evidence only.
  - Python does not import, invoke, or claim Rust runtime certification.
  - Hash parity witnesses remain pinned to Python and Rust tests.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_maf_receipt_parity_witness as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_maf_receipt_parity_witness_passes() -> None:
    errors = validator.validate_maf_receipt_parity_witness()
    witness = validator.load_json_object(validator.DEFAULT_WITNESS_PATH, "MafReceiptParityWitness")

    assert errors == []
    assert witness["witness_version"] == validator.EXPECTED_VERSION
    assert witness["solver_outcome"] == "AwaitingEvidence"
    assert witness["workspace_scope"]["foundation_mode"] is True
    assert witness["workspace_scope"]["rust_workspace_member_count"] == 11
    assert witness["contract_summary"]["hash_parity_witness_count"] == 2
    assert witness["contract_summary"]["crate_surface_mapping_count"] == 11
    assert witness["authority_boundary"]["rust_certifies_python_claimed"] is False
    assert validator.validate_maf_receipt_parity_witness_record(witness) == []


def test_maf_receipt_parity_witness_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_maf_receipt_parity_witness(
        authority_boundary__pyo3_binding_present=True,
        authority_boundary__python_imports_rust_runtime=True,
        authority_boundary__rust_subprocess_invoked=True,
        authority_boundary__maf_cli_invoked=True,
        authority_boundary__runtime_certification_claimed=True,
        authority_boundary__rust_certifies_python_claimed=True,
        authority_boundary__terminal_closure_allowed=True,
    )

    errors = validator.validate_maf_receipt_parity_witness_record(mutated)

    assert any("pyo3_binding_present" in error for error in errors)
    assert any("python_imports_rust_runtime" in error for error in errors)
    assert any("rust_subprocess_invoked" in error for error in errors)
    assert any("maf_cli_invoked" in error for error in errors)
    assert any("runtime_certification_claimed" in error for error in errors)
    assert any("rust_certifies_python_claimed" in error for error in errors)
    assert any("terminal_closure_allowed" in error for error in errors)
    assert any("solver_outcome cannot claim runtime parity" in error for error in errors)


def test_maf_receipt_parity_witness_rejects_hash_drift() -> None:
    mutated = validator.build_mutated_maf_receipt_parity_witness(
        hash_parity_witnesses__0__expected_sha256="0" * 64,
        hash_parity_witnesses__0__parity_status="schema_surface_mapped",
        hash_parity_witnesses__1__expected_sha256="1" * 64,
    )

    errors = validator.validate_maf_receipt_parity_witness_record(mutated)

    assert any("expected_sha256 must match canonical constant" in error for error in errors)
    assert any("expected hash missing from Python test" in error for error in errors)
    assert any("expected hash missing from Rust test" in error for error in errors)
    assert any("parity_status must be test_time_hash_parity_verified" in error for error in errors)


def test_maf_receipt_parity_witness_rejects_workspace_member_drift() -> None:
    mutated = validator.build_mutated_maf_receipt_parity_witness(
        workspace_scope__rust_workspace_member_count=1,
        crate_surface_mappings__0__rust_crate="maf-missing",
        crate_surface_mappings__0__rust_surface_ref="maf/rust/crates/maf-missing/src/lib.rs",
    )

    errors = validator.validate_maf_receipt_parity_witness_record(mutated)

    assert any("rust_workspace_member_count" in error for error in errors)
    assert any("missing crate: maf-kernel" in error for error in errors)
    assert any("unexpected crate: maf-missing" in error for error in errors)
    assert any("rust_crate missing from Cargo workspace" in error for error in errors)
    assert any("rust_surface_ref path missing" in error for error in errors)


def test_maf_receipt_parity_witness_rejects_missing_gap_refs() -> None:
    mutated = validator.build_mutated_maf_receipt_parity_witness(
        crate_surface_mappings__3__gap_refs=[],
        gap_refs=[],
        solver_outcome="SolvedUnverified",
    )

    errors = validator.validate_maf_receipt_parity_witness_record(mutated)

    assert any("gap_refs required for awaiting parity status" in error for error in errors)
    assert any("gap_refs" in error for error in errors)
    assert any("solver_outcome must remain AwaitingEvidence" in error for error in errors)


def test_maf_receipt_parity_witness_rejects_summary_and_ref_drift() -> None:
    mutated = validator.build_mutated_maf_receipt_parity_witness(
        receipt_refs__rust_workspace_manifest="maf/rust/Other.toml",
        evidence_refs=["schemas/maf_receipt_parity_witness.schema.json"],
        contract_summary__hash_parity_witness_count=1,
        contract_summary__crate_surface_mapping_count=1,
        contract_summary__awaiting_runtime_binding_count=1,
        contract_summary__authority_denial_count=1,
        contract_summary__evidence_ref_count=1,
        contract_summary__gap_ref_count=1,
    )

    errors = validator.validate_maf_receipt_parity_witness_record(mutated)

    assert any("receipt_refs.rust_workspace_manifest" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)
    assert any("hash_parity_witness_count" in error for error in errors)
    assert any("crate_surface_mapping_count" in error for error in errors)
    assert any("awaiting_runtime_binding_count" in error for error in errors)
    assert any("authority_denial_count" in error for error in errors)
    assert any("evidence_ref_count" in error for error in errors)
    assert any("gap_ref_count" in error for error in errors)


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/maf_receipt_parity_witness.schema.json",
            "--witness",
            "examples/maf_receipt_parity_witness.foundation.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["schema_path"]).as_posix() == "schemas/maf_receipt_parity_witness.schema.json"
    assert Path(payload["witness_path"]).as_posix() == "examples/maf_receipt_parity_witness.foundation.json"
    assert payload["errors"] == []


def test_malformed_maf_receipt_parity_witness_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_maf_receipt_parity_witness_record(None, schema)
    list_errors = validator.validate_maf_receipt_parity_witness_record([], schema)

    assert any("MAF receipt parity witness must be a JSON object" in error for error in none_errors)
    assert any("MAF receipt parity witness must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_maf_receipt_parity_witness() -> None:
    requirement_path = Path("examples/sdlc/requirement_maf_receipt_parity_witness_20260616.json")
    design_path = Path("examples/sdlc/design_maf_receipt_parity_witness_20260616.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "MAF parity requirement")
    design = sdlc_validator.load_json_object(design_path, "MAF parity design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/maf_receipt_parity_witness.schema.json" in requirement["affected_surfaces"]
    assert "schemas/maf_receipt_parity_witness.schema.json" in design["schema_changes"]
    assert "scripts/validate_maf_receipt_parity_witness.py" in design["validator_changes"]
    assert "tests/test_validate_maf_receipt_parity_witness.py" in design["validator_changes"]
    assert "No PyO3, subprocess, MAF CLI, or runtime Rust binding authority" in requirement["non_goals"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True

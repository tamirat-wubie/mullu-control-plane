"""Purpose: verify MafReceiptParityWitness validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_maf_receipt_parity_witness and SDLC validator.
Invariants:
  - MAF parity remains digest-only until fixture, ABI, and failure witnesses exist.
  - PyO3, subprocess, CLI, Rust execution, connectors, writes, and closure remain denied.
  - Python schema and Rust crate refs remain hash-anchored.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_maf_receipt_parity_witness as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_maf_receipt_parity_digest_is_line_ending_stable(tmp_path: Path) -> None:
    lf_source = tmp_path / "source_lf.rs"
    crlf_source = tmp_path / "source_crlf.rs"
    lf_source.write_text("pub struct Receipt;\nfn main() {}\n", encoding="utf-8", newline="\n")
    crlf_source.write_text("pub struct Receipt;\nfn main() {}\n", encoding="utf-8", newline="\r\n")

    lf_digest = validator.canonical_source_digest(lf_source)
    crlf_digest = validator.canonical_source_digest(crlf_source)

    assert lf_digest == crlf_digest
    assert len(lf_digest) == 64
    assert all(character in "0123456789abcdef" for character in lf_digest)


def test_maf_receipt_parity_witness_passes() -> None:
    errors = validator.validate_maf_receipt_parity_witness()
    witness = validator.load_json_object(
        validator.DEFAULT_WITNESS_PATH,
        "MafReceiptParityWitness",
    )

    assert errors == []
    assert witness["witness_version"] == validator.EXPECTED_WITNESS_VERSION
    assert witness["solver_outcome"] == "AwaitingEvidence"
    assert witness["parity_scope"]["parity_mode"] == validator.EXPECTED_PARITY_MODE
    assert witness["parity_scope"]["runtime_binding_claimed"] is False
    assert witness["parity_scope"]["rust_execution_performed"] is False
    assert witness["authority_boundary"]["digest_only_static_read_allowed"] is True
    assert witness["authority_boundary"]["cli_execution_allowed"] is False
    assert witness["contract_summary"]["python_schema_surface_count"] == 10
    assert witness["contract_summary"]["rust_crate_surface_count"] == 11
    assert witness["contract_summary"]["parity_mapping_count"] == 11
    assert validator.validate_maf_receipt_parity_witness_record(witness) == []


def test_maf_receipt_parity_witness_rejects_runtime_authority_drift() -> None:
    mutated = validator.build_mutated_maf_receipt_parity_witness(
        parity_scope__runtime_binding_claimed=True,
        parity_scope__rust_execution_performed=True,
        parity_scope__python_to_rust_call_path_claimed=True,
        parity_scope__direct_runtime_binding_deferred=False,
        authority_boundary__pyo3_binding_allowed=True,
        authority_boundary__subprocess_execution_allowed=True,
        authority_boundary__cli_execution_allowed=True,
        authority_boundary__rust_crate_execution_allowed=True,
        authority_boundary__external_connector_call_allowed=True,
        authority_boundary__filesystem_write_allowed=True,
        authority_boundary__terminal_closure_allowed=True,
        authority_boundary__success_claim_allowed=True,
        solver_outcome="SolvedUnverified",
    )

    errors = validator.validate_maf_receipt_parity_witness_record(mutated)

    assert any("runtime_binding_claimed" in error for error in errors)
    assert any("rust_execution_performed" in error for error in errors)
    assert any("python_to_rust_call_path_claimed" in error for error in errors)
    assert any("direct_runtime_binding_deferred" in error for error in errors)
    assert any("pyo3_binding_allowed" in error for error in errors)
    assert any("subprocess_execution_allowed" in error for error in errors)
    assert any("cli_execution_allowed" in error for error in errors)
    assert any("rust_crate_execution_allowed" in error for error in errors)
    assert any("external_connector_call_allowed" in error for error in errors)
    assert any("filesystem_write_allowed" in error for error in errors)
    assert any("terminal_closure_allowed" in error for error in errors)
    assert any("success_claim_allowed" in error for error in errors)
    assert any("solver_outcome must remain AwaitingEvidence" in error for error in errors)


def test_maf_receipt_parity_witness_rejects_python_schema_digest_drift() -> None:
    mutated = validator.build_mutated_maf_receipt_parity_witness(
        python_schema_surfaces__0__schema_digest_sha256="0" * 64,
    )

    errors = validator.validate_maf_receipt_parity_witness_record(mutated)

    assert any("schema_digest_sha256 does not match source digest" in error for error in errors)
    assert any("schemas/sdlc_transition_receipt.schema.json" in error for error in errors)
    assert len(errors) >= 1


def test_maf_receipt_parity_witness_rejects_rust_crate_digest_drift() -> None:
    mutated = validator.build_mutated_maf_receipt_parity_witness(
        rust_crate_surfaces__0__crate_entry_ref="maf/rust/crates/maf-event/src/lib.rs",
        rust_crate_surfaces__0__crate_entry_digest_sha256="1" * 64,
        rust_crate_surfaces__0__execution_authority_denied=False,
    )

    errors = validator.validate_maf_receipt_parity_witness_record(mutated)

    assert any("maf-kernel crate_entry_ref" in error for error in errors)
    assert any("crate_entry_digest_sha256 does not match source digest" in error for error in errors)
    assert any("maf-kernel execution_authority_denied must be true" in error for error in errors)


def test_maf_receipt_parity_witness_rejects_gap_closure_without_evidence() -> None:
    mutated = validator.build_mutated_maf_receipt_parity_witness(
        parity_mappings__0__parity_status="authority_denied",
        parity_mappings__0__rust_crate_name="maf-kernel",
        parity_mappings__0__gap_refs=[],
        parity_mappings__0__runtime_binding_allowed=True,
        parity_scope__required_future_witnesses=["witness://maf/abi-cli-contract"],
        solver_outcome="SolvedUnverified",
    )

    errors = validator.validate_maf_receipt_parity_witness_record(mutated)

    assert any("gap_refs required" in error for error in errors)
    assert any("runtime_binding_allowed must be false" in error for error in errors)
    assert any("authority_denied is only valid for maf-cli" in error for error in errors)
    assert any("required_future_witnesses missing required ref" in error for error in errors)
    assert any("solver_outcome must remain AwaitingEvidence" in error for error in errors)


def test_maf_receipt_parity_witness_rejects_summary_drift() -> None:
    mutated = validator.build_mutated_maf_receipt_parity_witness(
        contract_summary__python_schema_surface_count=1,
        contract_summary__rust_crate_surface_count=1,
        contract_summary__parity_mapping_count=1,
        contract_summary__authority_denial_count=1,
        contract_summary__awaiting_gap_count=1,
        contract_summary__evidence_ref_count=1,
    )

    errors = validator.validate_maf_receipt_parity_witness_record(mutated)

    assert any("python_schema_surface_count" in error for error in errors)
    assert any("rust_crate_surface_count" in error for error in errors)
    assert any("parity_mapping_count" in error for error in errors)
    assert any("authority_denial_count" in error for error in errors)
    assert any("awaiting_gap_count" in error for error in errors)
    assert any("evidence_ref_count" in error for error in errors)


def test_maf_receipt_parity_witness_rejects_missing_refs_and_secrets() -> None:
    mutated = validator.build_mutated_maf_receipt_parity_witness(
        receipt_refs__maf_boundary_doc="maf/OTHER.md",
        evidence_refs=["schemas/maf_receipt_parity_witness.schema.json"],
    )
    mutated["secret_probe"] = "client_secret"

    errors = validator.validate_maf_receipt_parity_witness_record(mutated)

    assert any("receipt_refs.maf_boundary_doc" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)
    assert any("secret marker is not allowed" in error for error in errors)
    assert any("unexpected property 'secret_probe'" in error for error in errors)


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

    assert any("maf receipt parity witness must be a JSON object" in error for error in none_errors)
    assert any("maf receipt parity witness must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_maf_receipt_parity_witness() -> None:
    requirement_path = Path("examples/sdlc/requirement_maf_receipt_parity_witness_20260618.json")
    design_path = Path("examples/sdlc/design_maf_receipt_parity_witness_20260618.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "maf receipt parity requirement")
    design = sdlc_validator.load_json_object(design_path, "maf receipt parity design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/maf_receipt_parity_witness.schema.json" in requirement["affected_surfaces"]
    assert "schemas/maf_receipt_parity_witness.schema.json" in design["schema_changes"]
    assert "scripts/validate_maf_receipt_parity_witness.py" in design["validator_changes"]
    assert "tests/test_validate_maf_receipt_parity_witness.py" in design["validator_changes"]
    assert "no PyO3 binding" in requirement["non_goals"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True

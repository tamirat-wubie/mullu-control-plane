"""Purpose: verify MafRuntimeBindingAdmissionWitness validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_maf_runtime_binding_admission_witness and SDLC validator.
Invariants:
  - MAF runtime binding admission remains evidence-gated.
  - Runtime binding, implementation start, PyO3, subprocess, default flip, and closure stay denied.
  - Static prerequisite closure cannot be overclaimed as executable binding.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_maf_runtime_binding_admission_witness as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_maf_runtime_binding_admission_digest_is_line_ending_stable(tmp_path: Path) -> None:
    lf_source = tmp_path / "source_lf.txt"
    crlf_source = tmp_path / "source_crlf.txt"
    lf_source.write_text("runtime-binding\n", encoding="utf-8", newline="\n")
    crlf_source.write_text("runtime-binding\n", encoding="utf-8", newline="\r\n")

    lf_digest = validator.canonical_source_digest(lf_source)
    crlf_digest = validator.canonical_source_digest(crlf_source)

    assert lf_digest == crlf_digest
    assert len(lf_digest) == 64
    assert all(character in "0123456789abcdef" for character in lf_digest)


def test_maf_runtime_binding_admission_witness_passes() -> None:
    errors = validator.validate_maf_runtime_binding_admission_witness()
    witness = validator.load_json_object(
        validator.DEFAULT_WITNESS_PATH,
        "MafRuntimeBindingAdmissionWitness",
    )

    assert errors == []
    assert witness["witness_version"] == validator.EXPECTED_WITNESS_VERSION
    assert witness["solver_outcome"] == "AwaitingEvidence"
    assert witness["admission_scope"]["admission_mode"] == validator.EXPECTED_ADMISSION_MODE
    assert witness["admission_scope"]["static_prerequisites_closed"] is True
    assert witness["admission_scope"]["runtime_binding_admission_recorded"] is True
    assert witness["admission_scope"]["runtime_binding_claimed"] is False
    assert witness["admission_scope"]["implementation_authority_claimed"] is False
    assert witness["admission_scope"]["terminal_closure_claimed"] is False
    assert set(witness["admission_scope"]["required_implementation_evidence"]) == validator.REQUIRED_IMPLEMENTATION_EVIDENCE
    assert witness["authority_boundary"]["static_admission_read_allowed"] is True
    assert witness["authority_boundary"]["runtime_binding_allowed"] is False
    assert witness["authority_boundary"]["implementation_start_allowed"] is False
    assert witness["authority_boundary"]["default_backend_flip_allowed"] is False
    assert witness["contract_summary"]["admission_requirement_count"] == 6
    assert validator.validate_maf_runtime_binding_admission_witness_record(witness) == []


def test_maf_runtime_binding_admission_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_maf_runtime_binding_admission_witness(
        admission_scope__runtime_binding_claimed=True,
        admission_scope__implementation_authority_claimed=True,
        admission_scope__terminal_closure_claimed=True,
        authority_boundary__implementation_start_allowed=True,
        authority_boundary__runtime_binding_allowed=True,
        authority_boundary__pyo3_binding_allowed=True,
        authority_boundary__subprocess_execution_allowed=True,
        authority_boundary__ci_rust_backend_required_allowed=True,
        authority_boundary__default_backend_flip_allowed=True,
        authority_boundary__terminal_closure_allowed=True,
        authority_boundary__success_claim_allowed=True,
        solver_outcome="SolvedUnverified",
    )

    errors = validator.validate_maf_runtime_binding_admission_witness_record(mutated)

    assert any("runtime_binding_claimed" in error for error in errors)
    assert any("implementation_authority_claimed" in error for error in errors)
    assert any("terminal_closure_claimed" in error for error in errors)
    assert any("implementation_start_allowed" in error for error in errors)
    assert any("runtime_binding_allowed" in error for error in errors)
    assert any("pyo3_binding_allowed" in error for error in errors)
    assert any("subprocess_execution_allowed" in error for error in errors)
    assert any("ci_rust_backend_required_allowed" in error for error in errors)
    assert any("default_backend_flip_allowed" in error for error in errors)
    assert any("terminal_closure_allowed" in error for error in errors)
    assert any("success_claim_allowed" in error for error in errors)
    assert any("solver_outcome must remain AwaitingEvidence" in error for error in errors)


def test_maf_runtime_binding_admission_rejects_scope_and_evidence_drift() -> None:
    mutated = validator.build_mutated_maf_runtime_binding_admission_witness(
        admission_scope__foundation_mode=False,
        admission_scope__admission_mode="runtime_binding_enabled",
        admission_scope__static_prerequisites_closed=False,
        admission_scope__runtime_binding_admission_recorded=False,
        admission_scope__required_implementation_evidence=["evidence://maf/runtime-binding/implementation-design"],
    )

    errors = validator.validate_maf_runtime_binding_admission_witness_record(mutated)

    assert any("foundation_mode" in error for error in errors)
    assert any("admission_mode" in error for error in errors)
    assert any("static_prerequisites_closed" in error for error in errors)
    assert any("runtime_binding_admission_recorded" in error for error in errors)
    assert any("required_implementation_evidence" in error for error in errors)


def test_maf_runtime_binding_admission_rejects_requirement_drift() -> None:
    mutated = validator.build_mutated_maf_runtime_binding_admission_witness()
    mutated["admission_requirements"][0]["execution_allowed"] = True
    mutated["admission_requirements"][0]["evidence_state"] = "Pass"
    mutated["admission_requirements"][0]["admission_status"] = "admitted"
    mutated["admission_requirements"] = mutated["admission_requirements"][:5]

    errors = validator.validate_maf_runtime_binding_admission_witness_record(mutated)

    assert any("admission_requirements must cover exactly" in error for error in errors)
    assert any("execution_allowed must remain false" in error for error in errors)
    assert any("evidence_state must remain AwaitingEvidence" in error for error in errors)
    assert any("admission_status must remain blocked_until_evidence" in error for error in errors)
    assert any("missing admission requirement" in error for error in errors)


def test_maf_runtime_binding_admission_rejects_digest_and_summary_drift() -> None:
    mutated = validator.build_mutated_maf_runtime_binding_admission_witness(
        contract_summary__source_artifact_count=0,
        contract_summary__admission_requirement_count=0,
        contract_summary__authority_denial_count=0,
        contract_summary__open_evidence_count=0,
        contract_summary__evidence_ref_count=0,
    )
    mutated["source_artifacts"][0]["artifact_digest_sha256"] = "0" * 64

    errors = validator.validate_maf_runtime_binding_admission_witness_record(mutated)

    assert any("digest drift" in error for error in errors)
    assert any("source_artifact_count" in error for error in errors)
    assert any("admission_requirement_count" in error for error in errors)
    assert any("authority_denial_count" in error for error in errors)
    assert any("open_evidence_count" in error for error in errors)
    assert any("evidence_ref_count" in error for error in errors)


def test_maf_runtime_binding_admission_rejects_receipt_ref_and_gap_drift() -> None:
    mutated = validator.build_mutated_maf_runtime_binding_admission_witness()
    mutated["receipt_refs"]["maf_f8_scoping_plan"] = "docs/MAF_FFI.md"
    mutated["evidence_refs"] = ["witness://maf/receipt-parity"]

    errors = validator.validate_maf_runtime_binding_admission_witness_record(mutated)

    assert any("receipt_refs.maf_f8_scoping_plan" in error for error in errors)
    assert any("runtime binding implementation evidence gap" in error for error in errors)
    assert any("failure receipt path witness ref" in error for error in errors)


def test_maf_runtime_binding_admission_cli_json_output() -> None:
    errors = validator.validate_maf_runtime_binding_admission_witness()
    payload = {"ok": not errors, "errors": errors}

    encoded = json.dumps(payload, indent=2, sort_keys=True)

    assert '"ok": true' in encoded
    assert payload["errors"] == []
    assert payload["ok"] is True


def test_sdlc_requirement_and_design_validate_for_maf_runtime_binding_admission() -> None:
    requirement_path = Path("examples/sdlc/requirement_maf_runtime_binding_admission_witness_20260618.json")
    design_path = Path("examples/sdlc/design_maf_runtime_binding_admission_witness_20260618.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "maf runtime binding admission requirement")
    design = sdlc_validator.load_json_object(design_path, "maf runtime binding admission design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert "schemas/maf_runtime_binding_admission_witness.schema.json" in requirement["affected_surfaces"]
    assert "scripts/validate_maf_runtime_binding_admission_witness.py" in design["validator_changes"]

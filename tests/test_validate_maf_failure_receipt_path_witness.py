"""Purpose: verify MafFailureReceiptPathWitness validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_maf_failure_receipt_path_witness and SDLC validator.
Invariants:
  - MAF failure receipt path closure is static and digest-only.
  - Runtime binding, CLI, subprocess, writes, raw failure payload retention, and closure remain denied.
  - Runtime binding can only be reconsidered by later governed implementation evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_maf_failure_receipt_path_witness as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_maf_failure_receipt_path_digest_is_line_ending_stable(tmp_path: Path) -> None:
    lf_source = tmp_path / "source_lf.txt"
    crlf_source = tmp_path / "source_crlf.txt"
    lf_source.write_text("failure\n", encoding="utf-8", newline="\n")
    crlf_source.write_text("failure\n", encoding="utf-8", newline="\r\n")

    lf_digest = validator.canonical_source_digest(lf_source)
    crlf_digest = validator.canonical_source_digest(crlf_source)

    assert lf_digest == crlf_digest
    assert len(lf_digest) == 64
    assert all(character in "0123456789abcdef" for character in lf_digest)


def test_maf_failure_receipt_path_witness_passes() -> None:
    errors = validator.validate_maf_failure_receipt_path_witness()
    witness = validator.load_json_object(
        validator.DEFAULT_WITNESS_PATH,
        "MafFailureReceiptPathWitness",
    )

    assert errors == []
    assert witness["witness_version"] == validator.EXPECTED_WITNESS_VERSION
    assert witness["solver_outcome"] == "AwaitingEvidence"
    assert witness["path_scope"]["path_mode"] == validator.EXPECTED_PATH_MODE
    assert witness["path_scope"]["failure_receipt_path_closed"] is True
    assert witness["path_scope"]["required_future_witnesses"] == []
    assert witness["path_scope"]["runtime_binding_reconsideration_only"] is True
    assert witness["authority_boundary"]["static_failure_path_read_allowed"] is True
    assert witness["authority_boundary"]["runtime_binding_allowed"] is False
    assert witness["authority_boundary"]["cli_execution_allowed"] is False
    assert witness["authority_boundary"]["subprocess_execution_allowed"] is False
    assert witness["authority_boundary"]["raw_failure_payload_retention_allowed"] is False
    assert witness["contract_summary"]["failure_path_control_count"] == 3
    assert validator.validate_maf_failure_receipt_path_witness_record(witness) == []


def test_maf_failure_receipt_path_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_maf_failure_receipt_path_witness(
        path_scope__runtime_binding_claimed=True,
        path_scope__subprocess_execution_claimed=True,
        path_scope__cli_execution_claimed=True,
        path_scope__command_behavior_claimed=True,
        authority_boundary__runtime_binding_allowed=True,
        authority_boundary__cli_execution_allowed=True,
        authority_boundary__subprocess_execution_allowed=True,
        authority_boundary__raw_failure_payload_retention_allowed=True,
        authority_boundary__filesystem_write_allowed=True,
        authority_boundary__terminal_closure_allowed=True,
        authority_boundary__success_claim_allowed=True,
        solver_outcome="SolvedUnverified",
    )

    errors = validator.validate_maf_failure_receipt_path_witness_record(mutated)

    assert any("runtime_binding_claimed" in error for error in errors)
    assert any("subprocess_execution_claimed" in error for error in errors)
    assert any("cli_execution_claimed" in error for error in errors)
    assert any("command_behavior_claimed" in error for error in errors)
    assert any("runtime_binding_allowed" in error for error in errors)
    assert any("cli_execution_allowed" in error for error in errors)
    assert any("subprocess_execution_allowed" in error for error in errors)
    assert any("raw_failure_payload_retention_allowed" in error for error in errors)
    assert any("filesystem_write_allowed" in error for error in errors)
    assert any("terminal_closure_allowed" in error for error in errors)
    assert any("success_claim_allowed" in error for error in errors)
    assert any("solver_outcome must remain AwaitingEvidence" in error for error in errors)


def test_maf_failure_receipt_path_rejects_scope_and_future_drift() -> None:
    mutated = validator.build_mutated_maf_failure_receipt_path_witness(
        path_scope__foundation_mode=False,
        path_scope__path_mode="runtime_failure_receipt_path",
        path_scope__failure_receipt_path_closed=False,
        path_scope__runtime_binding_reconsideration_only=False,
        path_scope__required_future_witnesses=["witness://maf/failure-receipt-path"],
    )

    errors = validator.validate_maf_failure_receipt_path_witness_record(mutated)

    assert any("foundation_mode" in error for error in errors)
    assert any("path_mode" in error for error in errors)
    assert any("failure_receipt_path_closed" in error for error in errors)
    assert any("runtime_binding_reconsideration_only" in error for error in errors)
    assert any("required_future_witnesses" in error for error in errors)
    assert any("closed failure receipt path witness" in error for error in errors)


def test_maf_failure_receipt_path_rejects_control_drift() -> None:
    mutated = validator.build_mutated_maf_failure_receipt_path_witness()
    mutated["failure_path_controls"][0]["runtime_materialization_allowed"] = True
    mutated["failure_path_controls"][0]["raw_failure_payload_retained"] = True
    mutated["failure_path_controls"][0]["path_descriptor_digest_sha256"] = "0" * 64
    mutated["failure_path_controls"] = mutated["failure_path_controls"][:2]

    errors = validator.validate_maf_failure_receipt_path_witness_record(mutated)

    assert any("failure_path_controls must cover exactly" in error for error in errors)
    assert any("runtime_materialization_allowed must remain false" in error for error in errors)
    assert any("raw_failure_payload_retained must remain false" in error for error in errors)
    assert any("path descriptor digest drift" in error for error in errors)
    assert any("missing failure path control for emit-transition-receipt" in error for error in errors)


def test_maf_failure_receipt_path_rejects_digest_and_summary_drift() -> None:
    mutated = validator.build_mutated_maf_failure_receipt_path_witness(
        contract_summary__source_artifact_count=0,
        contract_summary__failure_path_control_count=0,
        contract_summary__authority_denial_count=0,
        contract_summary__open_gap_count=1,
        contract_summary__evidence_ref_count=0,
    )
    mutated["source_artifacts"][0]["artifact_digest_sha256"] = "0" * 64

    errors = validator.validate_maf_failure_receipt_path_witness_record(mutated)

    assert any("digest drift" in error for error in errors)
    assert any("source_artifact_count" in error for error in errors)
    assert any("failure_path_control_count" in error for error in errors)
    assert any("authority_denial_count" in error for error in errors)
    assert any("open_gap_count" in error for error in errors)
    assert any("evidence_ref_count" in error for error in errors)


def test_maf_failure_receipt_path_rejects_receipt_ref_and_evidence_drift() -> None:
    mutated = validator.build_mutated_maf_failure_receipt_path_witness()
    mutated["receipt_refs"]["rust_cli_entry"] = "maf/rust/crates/maf-cli/src/lib.rs"
    mutated["evidence_refs"] = ["gap://maf/failure-receipt-path-open"]

    errors = validator.validate_maf_failure_receipt_path_witness_record(mutated)

    assert any("receipt_refs.rust_cli_entry" in error for error in errors)
    assert any("failure receipt path witness ref" in error for error in errors)
    assert any("must not retain the open failure receipt path gap" in error for error in errors)


def test_maf_failure_receipt_path_cli_json_output() -> None:
    errors = validator.validate_maf_failure_receipt_path_witness()
    payload = {"ok": not errors, "errors": errors}

    encoded = json.dumps(payload, indent=2, sort_keys=True)

    assert '"ok": true' in encoded
    assert payload["errors"] == []
    assert payload["ok"] is True


def test_sdlc_requirement_and_design_validate_for_maf_failure_receipt_path() -> None:
    requirement_path = Path("examples/sdlc/requirement_maf_failure_receipt_path_witness_20260618.json")
    design_path = Path("examples/sdlc/design_maf_failure_receipt_path_witness_20260618.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "maf failure receipt path requirement")
    design = sdlc_validator.load_json_object(design_path, "maf failure receipt path design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert "schemas/maf_failure_receipt_path_witness.schema.json" in requirement["affected_surfaces"]
    assert "scripts/validate_maf_failure_receipt_path_witness.py" in design["validator_changes"]

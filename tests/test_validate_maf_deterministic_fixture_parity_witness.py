"""Purpose: verify MafDeterministicFixtureParityWitness validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_maf_deterministic_fixture_parity_witness and SDLC validator.
Invariants:
  - MAF deterministic fixture parity is static and digest-only.
  - CLI, subprocess, runtime binding, writes, raw payload retention, and closure remain denied.
  - Failure receipt path remains AwaitingEvidence.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_maf_deterministic_fixture_parity_witness as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_maf_deterministic_fixture_parity_digest_is_line_ending_stable(tmp_path: Path) -> None:
    lf_source = tmp_path / "source_lf.txt"
    crlf_source = tmp_path / "source_crlf.txt"
    lf_source.write_text("fixture\n", encoding="utf-8", newline="\n")
    crlf_source.write_text("fixture\n", encoding="utf-8", newline="\r\n")

    lf_digest = validator.canonical_source_digest(lf_source)
    crlf_digest = validator.canonical_source_digest(crlf_source)

    assert lf_digest == crlf_digest
    assert len(lf_digest) == 64
    assert all(character in "0123456789abcdef" for character in lf_digest)


def test_maf_deterministic_fixture_parity_witness_passes() -> None:
    errors = validator.validate_maf_deterministic_fixture_parity_witness()
    witness = validator.load_json_object(
        validator.DEFAULT_WITNESS_PATH,
        "MafDeterministicFixtureParityWitness",
    )

    assert errors == []
    assert witness["witness_version"] == validator.EXPECTED_WITNESS_VERSION
    assert witness["solver_outcome"] == "AwaitingEvidence"
    assert witness["parity_scope"]["parity_mode"] == validator.EXPECTED_PARITY_MODE
    assert witness["parity_scope"]["deterministic_fixture_parity_closed"] is True
    assert set(witness["parity_scope"]["required_future_witnesses"]) == validator.REQUIRED_REMAINING_WITNESSES
    assert witness["authority_boundary"]["static_fixture_read_allowed"] is True
    assert witness["authority_boundary"]["cli_execution_allowed"] is False
    assert witness["authority_boundary"]["subprocess_execution_allowed"] is False
    assert witness["authority_boundary"]["raw_fixture_payload_retention_allowed"] is False
    assert witness["contract_summary"]["fixture_vector_count"] == 3
    assert validator.validate_maf_deterministic_fixture_parity_witness_record(witness) == []


def test_maf_deterministic_fixture_parity_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_maf_deterministic_fixture_parity_witness(
        parity_scope__runtime_binding_claimed=True,
        parity_scope__subprocess_execution_claimed=True,
        parity_scope__cli_execution_claimed=True,
        parity_scope__command_behavior_claimed=True,
        authority_boundary__cli_execution_allowed=True,
        authority_boundary__subprocess_execution_allowed=True,
        authority_boundary__runtime_binding_allowed=True,
        authority_boundary__raw_fixture_payload_retention_allowed=True,
        authority_boundary__filesystem_write_allowed=True,
        authority_boundary__terminal_closure_allowed=True,
        authority_boundary__success_claim_allowed=True,
        solver_outcome="SolvedUnverified",
    )

    errors = validator.validate_maf_deterministic_fixture_parity_witness_record(mutated)

    assert any("runtime_binding_claimed" in error for error in errors)
    assert any("subprocess_execution_claimed" in error for error in errors)
    assert any("cli_execution_claimed" in error for error in errors)
    assert any("command_behavior_claimed" in error for error in errors)
    assert any("cli_execution_allowed" in error for error in errors)
    assert any("subprocess_execution_allowed" in error for error in errors)
    assert any("runtime_binding_allowed" in error for error in errors)
    assert any("raw_fixture_payload_retention_allowed" in error for error in errors)
    assert any("filesystem_write_allowed" in error for error in errors)
    assert any("terminal_closure_allowed" in error for error in errors)
    assert any("success_claim_allowed" in error for error in errors)
    assert any("solver_outcome must remain AwaitingEvidence" in error for error in errors)


def test_maf_deterministic_fixture_parity_rejects_scope_and_future_drift() -> None:
    mutated = validator.build_mutated_maf_deterministic_fixture_parity_witness(
        parity_scope__foundation_mode=False,
        parity_scope__parity_mode="runtime_fixture_parity",
        parity_scope__deterministic_fixture_parity_closed=False,
        parity_scope__required_future_witnesses=[
            "witness://maf/deterministic-fixture-parity",
            "witness://maf/failure-receipt-path",
        ],
    )

    errors = validator.validate_maf_deterministic_fixture_parity_witness_record(mutated)

    assert any("foundation_mode" in error for error in errors)
    assert any("parity_mode" in error for error in errors)
    assert any("deterministic_fixture_parity_closed" in error for error in errors)
    assert any("required_future_witnesses" in error for error in errors)
    assert any("closed fixture parity witness" in error for error in errors)


def test_maf_deterministic_fixture_parity_rejects_fixture_vector_drift() -> None:
    mutated = validator.build_mutated_maf_deterministic_fixture_parity_witness()
    mutated["fixture_vectors"][0]["execution_allowed"] = True
    mutated["fixture_vectors"][0]["raw_payload_retained"] = True
    mutated["fixture_vectors"][0]["fixture_material_digest_sha256"] = "0" * 64
    mutated["fixture_vectors"][0]["failure_path_blocked_by"] = "witness://maf/deterministic-fixture-parity"
    mutated["fixture_vectors"] = mutated["fixture_vectors"][:2]

    errors = validator.validate_maf_deterministic_fixture_parity_witness_record(mutated)

    assert any("fixture_vectors must cover exactly" in error for error in errors)
    assert any("execution_allowed must remain false" in error for error in errors)
    assert any("raw_payload_retained must remain false" in error for error in errors)
    assert any("fixture digest drift" in error for error in errors)
    assert any("missing fixture vector for emit-transition-receipt" in error for error in errors)


def test_maf_deterministic_fixture_parity_rejects_digest_and_summary_drift() -> None:
    mutated = validator.build_mutated_maf_deterministic_fixture_parity_witness(
        contract_summary__source_artifact_count=0,
        contract_summary__fixture_vector_count=0,
        contract_summary__authority_denial_count=0,
        contract_summary__open_gap_count=0,
        contract_summary__evidence_ref_count=0,
    )
    mutated["source_artifacts"][0]["artifact_digest_sha256"] = "0" * 64

    errors = validator.validate_maf_deterministic_fixture_parity_witness_record(mutated)

    assert any("digest drift" in error for error in errors)
    assert any("source_artifact_count" in error for error in errors)
    assert any("fixture_vector_count" in error for error in errors)
    assert any("authority_denial_count" in error for error in errors)
    assert any("open_gap_count" in error for error in errors)
    assert any("evidence_ref_count" in error for error in errors)


def test_maf_deterministic_fixture_parity_rejects_receipt_ref_and_evidence_drift() -> None:
    mutated = validator.build_mutated_maf_deterministic_fixture_parity_witness()
    mutated["receipt_refs"]["rust_cli_entry"] = "maf/rust/crates/maf-cli/src/lib.rs"
    mutated["evidence_refs"] = ["witness://maf/subprocess-effect-boundary"]

    errors = validator.validate_maf_deterministic_fixture_parity_witness_record(mutated)

    assert any("receipt_refs.rust_cli_entry" in error for error in errors)
    assert any("deterministic fixture parity witness ref" in error for error in errors)
    assert any("failure receipt path gap" in error for error in errors)


def test_maf_deterministic_fixture_parity_cli_json_output() -> None:
    errors = validator.validate_maf_deterministic_fixture_parity_witness()
    payload = {"ok": not errors, "errors": errors}

    encoded = json.dumps(payload, indent=2, sort_keys=True)

    assert '"ok": true' in encoded
    assert payload["errors"] == []
    assert payload["ok"] is True


def test_sdlc_requirement_and_design_validate_for_maf_deterministic_fixture_parity() -> None:
    requirement_path = Path("examples/sdlc/requirement_maf_deterministic_fixture_parity_witness_20260618.json")
    design_path = Path("examples/sdlc/design_maf_deterministic_fixture_parity_witness_20260618.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "maf deterministic fixture requirement")
    design = sdlc_validator.load_json_object(design_path, "maf deterministic fixture design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert "schemas/maf_deterministic_fixture_parity_witness.schema.json" in requirement["affected_surfaces"]
    assert "scripts/validate_maf_deterministic_fixture_parity_witness.py" in design["validator_changes"]

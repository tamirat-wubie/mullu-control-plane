"""Purpose: verify MafAbiCliContractWitness validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_maf_abi_cli_contract_witness.
Invariants: ABI/CLI contract evidence remains witness-only and non-executing.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_maf_abi_cli_contract_witness as validator


def test_maf_abi_cli_digest_is_line_ending_stable(tmp_path: Path) -> None:
    lf_source = tmp_path / "source_lf.rs"
    crlf_source = tmp_path / "source_crlf.rs"
    lf_source.write_text("fn main() {}\n", encoding="utf-8", newline="\n")
    crlf_source.write_text("fn main() {}\n", encoding="utf-8", newline="\r\n")

    lf_digest = validator.canonical_source_digest(lf_source)
    crlf_digest = validator.canonical_source_digest(crlf_source)

    assert lf_digest == crlf_digest
    assert len(lf_digest) == 64
    assert all(character in "0123456789abcdef" for character in lf_digest)


def test_maf_abi_cli_contract_witness_passes() -> None:
    errors = validator.validate_maf_abi_cli_contract_witness()
    witness = validator.load_json_object(validator.DEFAULT_WITNESS_PATH, "MafAbiCliContractWitness")

    assert errors == []
    assert witness["witness_version"] == validator.EXPECTED_WITNESS_VERSION
    assert witness["solver_outcome"] == "AwaitingEvidence"
    assert witness["contract_scope"]["runtime_binding_claimed"] is False
    assert witness["contract_scope"]["cli_execution_performed"] is False
    assert witness["authority_boundary"]["cli_execution_allowed"] is False
    assert witness["authority_boundary"]["subprocess_execution_allowed"] is False
    assert witness["contract_summary"]["source_digest_count"] == 5
    assert witness["contract_summary"]["authority_denial_count"] == 12
    assert validator.validate_maf_abi_cli_contract_witness_record(witness) == []


def test_maf_abi_cli_contract_witness_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_maf_abi_cli_contract_witness(
        contract_scope__runtime_binding_claimed=True,
        contract_scope__cli_execution_performed=True,
        contract_scope__abi_stability_claimed=True,
        authority_boundary__cli_execution_allowed=True,
        authority_boundary__subprocess_execution_allowed=True,
        authority_boundary__rust_crate_execution_allowed=True,
        authority_boundary__python_to_rust_binding_allowed=True,
        authority_boundary__abi_stability_claim_allowed=True,
        authority_boundary__secret_access_allowed=True,
        authority_boundary__filesystem_write_allowed=True,
        authority_boundary__terminal_closure_allowed=True,
        authority_boundary__success_claim_allowed=True,
    )

    errors = validator.validate_maf_abi_cli_contract_witness_record(mutated)

    assert any("runtime_binding_claimed" in error for error in errors)
    assert any("cli_execution_performed" in error for error in errors)
    assert any("abi_stability_claimed" in error for error in errors)
    assert any("cli_execution_allowed" in error for error in errors)
    assert any("subprocess_execution_allowed" in error for error in errors)
    assert any("python_to_rust_binding_allowed" in error for error in errors)
    assert any("terminal_closure_allowed" in error for error in errors)
    assert any("success_claim_allowed" in error for error in errors)


def test_maf_abi_cli_contract_witness_rejects_digest_drift() -> None:
    mutated = validator.build_mutated_maf_abi_cli_contract_witness(
        source_digests__0__digest_sha256="0" * 64,
    )

    errors = validator.validate_maf_abi_cli_contract_witness_record(mutated)

    assert any("maf/rust/Cargo.toml" in error for error in errors)
    assert any("digest_sha256 does not match source digest" in error for error in errors)
    assert len(errors) >= 1


def test_maf_abi_cli_contract_witness_rejects_gap_closure_without_evidence() -> None:
    mutated = validator.build_mutated_maf_abi_cli_contract_witness(
        cli_contract__accepted_argument_schema_ref="schemas/maf_abi_cli_contract_witness.schema.json",
        cli_contract__output_receipt_schema_ref="schemas/maf_abi_cli_contract_witness.schema.json",
        contract_scope__required_future_witnesses=["witness://maf/subprocess-effect-boundary"],
    )

    errors = validator.validate_maf_abi_cli_contract_witness_record(mutated)

    assert any("accepted_argument_schema_ref cannot self-certify" in error for error in errors)
    assert any("accepted_argument_schema_ref must remain a gap ref" in error for error in errors)
    assert any("output_receipt_schema_ref must remain a gap ref" in error for error in errors)
    assert any("required_future_witnesses missing required ref" in error for error in errors)


def test_maf_abi_cli_contract_witness_rejects_summary_ref_and_secret_drift() -> None:
    mutated = validator.build_mutated_maf_abi_cli_contract_witness(
        receipt_refs__maf_abi_cli_contract_witness_schema="schemas/other.schema.json",
        contract_summary__source_digest_count=1,
        contract_summary__authority_denial_count=1,
        contract_summary__future_witness_count=1,
        contract_summary__evidence_ref_count=0,
        evidence_refs=["schemas/maf_abi_cli_contract_witness.schema.json"],
    )
    mutated["secret_probe"] = "client_secret"

    errors = validator.validate_maf_abi_cli_contract_witness_record(mutated)

    assert any("receipt_refs.maf_abi_cli_contract_witness_schema" in error for error in errors)
    assert any("contract_summary.source_digest_count" in error for error in errors)
    assert any("contract_summary.authority_denial_count" in error for error in errors)
    assert any("contract_summary.evidence_ref_count" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)
    assert any("secret marker is not allowed" in error for error in errors)
    assert any("unexpected property 'secret_probe'" in error for error in errors)


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main([
        "--schema",
        "schemas/maf_abi_cli_contract_witness.schema.json",
        "--witness",
        "examples/maf_abi_cli_contract_witness.foundation.json",
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["schema_path"]).as_posix() == "schemas/maf_abi_cli_contract_witness.schema.json"
    assert Path(payload["witness_path"]).as_posix() == "examples/maf_abi_cli_contract_witness.foundation.json"
    assert payload["errors"] == []


def test_malformed_maf_abi_cli_contract_witness_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_maf_abi_cli_contract_witness_record(None, schema)
    list_errors = validator.validate_maf_abi_cli_contract_witness_record([], schema)

    assert any("maf abi cli contract witness must be a JSON object" in error for error in none_errors)
    assert any("maf abi cli contract witness must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)

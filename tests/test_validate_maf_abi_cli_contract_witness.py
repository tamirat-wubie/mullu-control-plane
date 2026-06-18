"""Purpose: verify MafAbiCliContractWitness validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_maf_abi_cli_contract_witness and SDLC validator.
Invariants:
  - MAF CLI/ABI contract evidence remains scaffold-only.
  - CLI, subprocess, PyO3, Rust execution, connectors, writes, and closure remain denied.
  - Command behavior remains AwaitingEvidence until executable witnesses exist.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_maf_abi_cli_contract_witness as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_maf_abi_cli_contract_digest_is_line_ending_stable(tmp_path: Path) -> None:
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
    witness = validator.load_json_object(
        validator.DEFAULT_WITNESS_PATH,
        "MafAbiCliContractWitness",
    )

    assert errors == []
    assert witness["witness_version"] == validator.EXPECTED_WITNESS_VERSION
    assert witness["solver_outcome"] == "AwaitingEvidence"
    assert witness["abi_scope"]["contract_mode"] == validator.EXPECTED_CONTRACT_MODE
    assert witness["abi_scope"]["cli_scaffold_only"] is True
    assert witness["abi_scope"]["runtime_binding_claimed"] is False
    assert witness["abi_scope"]["command_behavior_claimed"] is False
    assert witness["authority_boundary"]["static_contract_read_allowed"] is True
    assert witness["authority_boundary"]["cli_execution_allowed"] is False
    assert witness["contract_summary"]["cli_artifact_count"] == 5
    assert witness["contract_summary"]["command_contract_count"] == 3
    assert validator.validate_maf_abi_cli_contract_witness_record(witness) == []


def test_maf_abi_cli_contract_witness_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_maf_abi_cli_contract_witness(
        abi_scope__runtime_binding_claimed=True,
        abi_scope__command_behavior_claimed=True,
        abi_scope__subprocess_effect_boundary_closed=True,
        authority_boundary__cli_execution_allowed=True,
        authority_boundary__subprocess_execution_allowed=True,
        authority_boundary__pyo3_binding_allowed=True,
        authority_boundary__rust_crate_execution_allowed=True,
        authority_boundary__external_connector_call_allowed=True,
        authority_boundary__filesystem_write_allowed=True,
        authority_boundary__terminal_closure_allowed=True,
        authority_boundary__success_claim_allowed=True,
        solver_outcome="SolvedUnverified",
    )

    errors = validator.validate_maf_abi_cli_contract_witness_record(mutated)

    assert any("runtime_binding_claimed" in error for error in errors)
    assert any("command_behavior_claimed" in error for error in errors)
    assert any("subprocess_effect_boundary_closed" in error for error in errors)
    assert any("cli_execution_allowed" in error for error in errors)
    assert any("subprocess_execution_allowed" in error for error in errors)
    assert any("pyo3_binding_allowed" in error for error in errors)
    assert any("rust_crate_execution_allowed" in error for error in errors)
    assert any("external_connector_call_allowed" in error for error in errors)
    assert any("filesystem_write_allowed" in error for error in errors)
    assert any("terminal_closure_allowed" in error for error in errors)
    assert any("success_claim_allowed" in error for error in errors)
    assert any("solver_outcome must remain AwaitingEvidence" in error for error in errors)


def test_maf_abi_cli_contract_witness_rejects_scaffold_and_command_drift() -> None:
    mutated = validator.build_mutated_maf_abi_cli_contract_witness(
        abi_scope__foundation_mode=False,
        abi_scope__contract_mode="runtime_cli_contract",
        abi_scope__cli_scaffold_only=False,
        abi_scope__required_future_witnesses=["witness://maf/subprocess-effect-boundary"],
        command_contracts__0__availability_status="Implemented",
        command_contracts__0__execution_allowed=True,
        command_contracts__0__gap_refs=[],
    )

    errors = validator.validate_maf_abi_cli_contract_witness_record(mutated)

    assert any("foundation_mode" in error for error in errors)
    assert any("contract_mode" in error for error in errors)
    assert any("cli_scaffold_only" in error for error in errors)
    assert any("required_future_witnesses missing required ref" in error for error in errors)
    assert any("availability_status must be AwaitingEvidence" in error for error in errors)
    assert any("execution_allowed must be false" in error for error in errors)
    assert any("gap_refs required" in error for error in errors)


def test_maf_abi_cli_contract_witness_rejects_digest_and_summary_drift() -> None:
    mutated = validator.build_mutated_maf_abi_cli_contract_witness(
        cli_artifacts__0__artifact_digest_sha256="0" * 64,
        cli_artifacts__0__execution_authority_denied=False,
        contract_summary__cli_artifact_count=1,
        contract_summary__command_contract_count=1,
        contract_summary__authority_denial_count=1,
        contract_summary__awaiting_gap_count=1,
        contract_summary__evidence_ref_count=1,
    )

    errors = validator.validate_maf_abi_cli_contract_witness_record(mutated)

    assert any("artifact_digest_sha256 does not match source digest" in error for error in errors)
    assert any("execution_authority_denied must be true" in error for error in errors)
    assert any("cli_artifact_count" in error for error in errors)
    assert any("command_contract_count" in error for error in errors)
    assert any("authority_denial_count" in error for error in errors)
    assert any("awaiting_gap_count" in error for error in errors)
    assert any("evidence_ref_count" in error for error in errors)


def test_maf_abi_cli_contract_witness_rejects_missing_refs_and_secrets() -> None:
    mutated = validator.build_mutated_maf_abi_cli_contract_witness(
        receipt_refs__maf_boundary_doc="maf/OTHER.md",
        evidence_refs=["schemas/maf_abi_cli_contract_witness.schema.json"],
    )
    mutated["secret_probe"] = "client_secret"

    errors = validator.validate_maf_abi_cli_contract_witness_record(mutated)

    assert any("receipt_refs.maf_boundary_doc" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)
    assert any("secret marker is not allowed" in error for error in errors)
    assert any("unexpected property 'secret_probe'" in error for error in errors)


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/maf_abi_cli_contract_witness.schema.json",
            "--witness",
            "examples/maf_abi_cli_contract_witness.foundation.json",
            "--json",
        ]
    )

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

    assert any("maf ABI CLI contract witness must be a JSON object" in error for error in none_errors)
    assert any("maf ABI CLI contract witness must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_maf_abi_cli_contract_witness() -> None:
    requirement_path = Path("examples/sdlc/requirement_maf_abi_cli_contract_witness_20260618.json")
    design_path = Path("examples/sdlc/design_maf_abi_cli_contract_witness_20260618.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "maf ABI CLI requirement")
    design = sdlc_validator.load_json_object(design_path, "maf ABI CLI design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/maf_abi_cli_contract_witness.schema.json" in requirement["affected_surfaces"]
    assert "schemas/maf_abi_cli_contract_witness.schema.json" in design["schema_changes"]
    assert "scripts/validate_maf_abi_cli_contract_witness.py" in design["validator_changes"]
    assert "tests/test_validate_maf_abi_cli_contract_witness.py" in design["validator_changes"]
    assert "no CLI execution" in requirement["non_goals"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True

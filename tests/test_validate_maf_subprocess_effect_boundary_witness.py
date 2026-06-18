"""Purpose: verify MafSubprocessEffectBoundaryWitness validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_maf_subprocess_effect_boundary_witness and SDLC validator.
Invariants:
  - MAF subprocess effect-boundary evidence is denied-by-default.
  - Subprocess, shell, child process, CLI execution, writes, secrets, raw retention, and closure remain denied.
  - Runtime binding remains AwaitingEvidence until fixture parity and failure receipts exist.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_maf_subprocess_effect_boundary_witness as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_maf_subprocess_effect_boundary_digest_is_line_ending_stable(tmp_path: Path) -> None:
    lf_source = tmp_path / "source_lf.txt"
    crlf_source = tmp_path / "source_crlf.txt"
    lf_source.write_text("boundary\n", encoding="utf-8", newline="\n")
    crlf_source.write_text("boundary\n", encoding="utf-8", newline="\r\n")

    lf_digest = validator.canonical_source_digest(lf_source)
    crlf_digest = validator.canonical_source_digest(crlf_source)

    assert lf_digest == crlf_digest
    assert len(lf_digest) == 64
    assert all(character in "0123456789abcdef" for character in lf_digest)


def test_maf_subprocess_effect_boundary_witness_passes() -> None:
    errors = validator.validate_maf_subprocess_effect_boundary_witness()
    witness = validator.load_json_object(
        validator.DEFAULT_WITNESS_PATH,
        "MafSubprocessEffectBoundaryWitness",
    )

    assert errors == []
    assert witness["witness_version"] == validator.EXPECTED_WITNESS_VERSION
    assert witness["solver_outcome"] == "AwaitingEvidence"
    assert witness["boundary_scope"]["boundary_mode"] == validator.EXPECTED_BOUNDARY_MODE
    assert witness["boundary_scope"]["subprocess_effect_boundary_closed"] is True
    assert witness["boundary_scope"]["runtime_binding_claimed"] is False
    assert witness["boundary_scope"]["subprocess_execution_claimed"] is False
    assert set(witness["boundary_scope"]["required_future_witnesses"]) == validator.REQUIRED_FUTURE_WITNESSES
    assert witness["authority_boundary"]["static_boundary_read_allowed"] is True
    assert witness["authority_boundary"]["subprocess_execution_allowed"] is False
    assert witness["authority_boundary"]["shell_invocation_allowed"] is False
    assert witness["authority_boundary"]["child_process_spawn_allowed"] is False
    assert witness["contract_summary"]["source_artifact_count"] == 7
    assert witness["contract_summary"]["effect_control_count"] == 12
    assert validator.validate_maf_subprocess_effect_boundary_witness_record(witness) == []


def test_maf_subprocess_effect_boundary_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_maf_subprocess_effect_boundary_witness(
        boundary_scope__runtime_binding_claimed=True,
        boundary_scope__subprocess_execution_claimed=True,
        authority_boundary__cli_execution_allowed=True,
        authority_boundary__subprocess_execution_allowed=True,
        authority_boundary__runtime_binding_allowed=True,
        authority_boundary__shell_invocation_allowed=True,
        authority_boundary__child_process_spawn_allowed=True,
        authority_boundary__raw_stdout_retention_allowed=True,
        authority_boundary__raw_stderr_retention_allowed=True,
        authority_boundary__filesystem_write_allowed=True,
        authority_boundary__terminal_closure_allowed=True,
        authority_boundary__success_claim_allowed=True,
        solver_outcome="SolvedUnverified",
    )

    errors = validator.validate_maf_subprocess_effect_boundary_witness_record(mutated)

    assert any("runtime_binding_claimed" in error for error in errors)
    assert any("subprocess_execution_claimed" in error for error in errors)
    assert any("cli_execution_allowed" in error for error in errors)
    assert any("subprocess_execution_allowed" in error for error in errors)
    assert any("runtime_binding_allowed" in error for error in errors)
    assert any("shell_invocation_allowed" in error for error in errors)
    assert any("child_process_spawn_allowed" in error for error in errors)
    assert any("raw_stdout_retention_allowed" in error for error in errors)
    assert any("raw_stderr_retention_allowed" in error for error in errors)
    assert any("filesystem_write_allowed" in error for error in errors)
    assert any("terminal_closure_allowed" in error for error in errors)
    assert any("success_claim_allowed" in error for error in errors)
    assert any("solver_outcome must remain AwaitingEvidence" in error for error in errors)


def test_maf_subprocess_effect_boundary_rejects_scope_and_gap_drift() -> None:
    mutated = validator.build_mutated_maf_subprocess_effect_boundary_witness(
        boundary_scope__foundation_mode=False,
        boundary_scope__boundary_mode="runtime_subprocess_execution",
        boundary_scope__subprocess_effect_boundary_closed=False,
        boundary_scope__required_future_witnesses=[
            "witness://maf/subprocess-effect-boundary",
            "witness://maf/deterministic-fixture-parity",
        ],
        effect_controls__0__boundary_status="runtime_allowed",
        effect_controls__0__execution_allowed=True,
        effect_controls__0__raw_retention_allowed=True,
        effect_controls__0__policy_ref="policy://other",
        effect_controls__0__gap_refs=["gap://maf/subprocess-effect-boundary-open"],
    )

    errors = validator.validate_maf_subprocess_effect_boundary_witness_record(mutated)

    assert any("foundation_mode" in error for error in errors)
    assert any("boundary_mode" in error for error in errors)
    assert any("subprocess_effect_boundary_closed" in error for error in errors)
    assert any("required_future_witnesses missing required ref" in error for error in errors)
    assert any("must not retain closed ref" in error for error in errors)
    assert any("boundary_status must be denied_until_witnessed" in error for error in errors)
    assert any("execution_allowed must be false" in error for error in errors)
    assert any("raw_retention_allowed must be false" in error for error in errors)
    assert any("policy_ref must use policy://maf/subprocess/" in error for error in errors)
    assert any("must not retain subprocess-effect-boundary-open gap" in error for error in errors)


def test_maf_subprocess_effect_boundary_rejects_digest_and_summary_drift() -> None:
    mutated = validator.build_mutated_maf_subprocess_effect_boundary_witness(
        source_artifacts__0__artifact_digest_sha256="0" * 64,
        source_artifacts__0__execution_authority_denied=False,
        contract_summary__source_artifact_count=1,
        contract_summary__effect_control_count=1,
        contract_summary__authority_denial_count=1,
        contract_summary__open_gap_count=1,
        contract_summary__evidence_ref_count=1,
    )

    errors = validator.validate_maf_subprocess_effect_boundary_witness_record(mutated)

    assert any("artifact_digest_sha256 does not match source digest" in error for error in errors)
    assert any("execution_authority_denied must be true" in error for error in errors)
    assert any("source_artifact_count" in error for error in errors)
    assert any("effect_control_count" in error for error in errors)
    assert any("authority_denial_count" in error for error in errors)
    assert any("open_gap_count" in error for error in errors)
    assert any("evidence_ref_count" in error for error in errors)


def test_maf_subprocess_effect_boundary_rejects_missing_refs_and_secrets() -> None:
    mutated = validator.build_mutated_maf_subprocess_effect_boundary_witness(
        receipt_refs__maf_boundary_doc="maf/OTHER.md",
        evidence_refs=["schemas/maf_subprocess_effect_boundary_witness.schema.json"],
    )
    mutated["secret_probe"] = "client_secret"

    errors = validator.validate_maf_subprocess_effect_boundary_witness_record(mutated)

    assert any("receipt_refs.maf_boundary_doc" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)
    assert any("secret marker is not allowed" in error for error in errors)
    assert any("unexpected property 'secret_probe'" in error for error in errors)


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/maf_subprocess_effect_boundary_witness.schema.json",
            "--witness",
            "examples/maf_subprocess_effect_boundary_witness.foundation.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["schema_path"]).as_posix() == "schemas/maf_subprocess_effect_boundary_witness.schema.json"
    assert Path(payload["witness_path"]).as_posix() == "examples/maf_subprocess_effect_boundary_witness.foundation.json"
    assert payload["errors"] == []


def test_malformed_maf_subprocess_effect_boundary_witness_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_maf_subprocess_effect_boundary_witness_record(None, schema)
    list_errors = validator.validate_maf_subprocess_effect_boundary_witness_record([], schema)

    assert any("maf subprocess effect boundary witness must be a JSON object" in error for error in none_errors)
    assert any("maf subprocess effect boundary witness must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_maf_subprocess_effect_boundary() -> None:
    requirement_path = Path("examples/sdlc/requirement_maf_subprocess_effect_boundary_witness_20260618.json")
    design_path = Path("examples/sdlc/design_maf_subprocess_effect_boundary_witness_20260618.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "maf subprocess boundary requirement")
    design = sdlc_validator.load_json_object(design_path, "maf subprocess boundary design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/maf_subprocess_effect_boundary_witness.schema.json" in requirement["affected_surfaces"]
    assert "schemas/maf_subprocess_effect_boundary_witness.schema.json" in design["schema_changes"]
    assert "scripts/validate_maf_subprocess_effect_boundary_witness.py" in design["validator_changes"]
    assert "tests/test_validate_maf_subprocess_effect_boundary_witness.py" in design["validator_changes"]
    assert "no subprocess execution" in requirement["non_goals"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True

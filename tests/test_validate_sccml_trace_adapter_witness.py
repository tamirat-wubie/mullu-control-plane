"""Purpose: verify SccmlTraceAdapterWitness validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_sccml_trace_adapter_witness and SDLC validator.
Invariants:
  - SCCML trace evidence remains witness-only.
  - Foundation Mode does not grant live kernel execution, subprocess execution,
    replay, state mutation, proof acceptance, connector, write, terminal, or
    success authority.
  - Raw traces, raw state, and secret values are not stored.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_sccml_trace_adapter_witness as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_sccml_trace_adapter_witness_passes() -> None:
    errors = validator.validate_sccml_trace_adapter_witness()
    witness = validator.load_json_object(validator.DEFAULT_WITNESS_PATH, "SccmlTraceAdapterWitness")

    assert errors == []
    assert witness["witness_version"] == validator.EXPECTED_WITNESS_VERSION
    assert witness["trace_scope"]["source_kernel_family"] == "symbolic-causal-chain-machine-language"
    assert witness["trace_scope"]["adapter_mode"] == "witness_only_operator_supplied_refs"
    assert witness["trace_scope"]["tenant_scope"] == "foundation-local-only"
    assert witness["authority_boundary"]["live_kernel_execution_performed"] is False
    assert witness["authority_boundary"]["governance_proof_accepted"] is False
    assert witness["trace_integrity_guard"]["unsupported_ops_declared"] is True
    assert witness["trace_integrity_guard"]["raw_trace_retained"] is False
    assert validator.validate_sccml_trace_adapter_witness_record(witness) == []


def test_sccml_trace_adapter_witness_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_sccml_trace_adapter_witness(
        authority_boundary__live_kernel_execution_performed=True,
        authority_boundary__subprocess_execution_performed=True,
        authority_boundary__external_repo_read_performed=True,
        authority_boundary__instruction_replay_performed=True,
        authority_boundary__state_mutation_performed=True,
        authority_boundary__proof_committed=True,
        authority_boundary__governance_proof_accepted=True,
        authority_boundary__connector_call_performed=True,
        authority_boundary__external_write_performed=True,
        authority_boundary__file_write_performed=True,
        authority_boundary__terminal_closure_allowed=True,
        authority_boundary__success_claim_allowed=True,
    )

    errors = validator.validate_sccml_trace_adapter_witness_record(mutated)

    assert any("authority_boundary.live_kernel_execution_performed" in error for error in errors)
    assert any("authority_boundary.subprocess_execution_performed" in error for error in errors)
    assert any("authority_boundary.external_repo_read_performed" in error for error in errors)
    assert any("authority_boundary.instruction_replay_performed" in error for error in errors)
    assert any("authority_boundary.state_mutation_performed" in error for error in errors)
    assert any("authority_boundary.proof_committed" in error for error in errors)
    assert any("authority_boundary.governance_proof_accepted" in error for error in errors)
    assert any("authority_boundary.terminal_closure_allowed" in error for error in errors)


def test_sccml_trace_adapter_witness_rejects_unsupported_op_silence() -> None:
    mutated = validator.build_mutated_sccml_trace_adapter_witness(
        authority_boundary__unsupported_op_ignored=True,
        trace_integrity_guard__unsupported_ops_declared=False,
        trace_scope__unsupported_op_gap_ref="",
        trace_artifacts__unsupported_ops_digest_ref="unsupported://raw-gap",
        contract_summary__unsupported_ops_gap_declared=False,
    )

    errors = validator.validate_sccml_trace_adapter_witness_record(mutated)

    assert any("authority_boundary.unsupported_op_ignored" in error for error in errors)
    assert any("trace_integrity_guard.unsupported_ops_declared" in error for error in errors)
    assert any("unsupported_op_gap_ref must be non-empty" in error for error in errors)
    assert any("unsupported_ops_digest_ref must use hash://sha256/" in error for error in errors)
    assert any("contract_summary.unsupported_ops_gap_declared" in error for error in errors)


def test_sccml_trace_adapter_witness_rejects_raw_trace_and_state_retention() -> None:
    mutated = validator.build_mutated_sccml_trace_adapter_witness(
        authority_boundary__raw_trace_stored=True,
        authority_boundary__raw_state_stored=True,
        authority_boundary__raw_secret_value_stored=True,
        trace_integrity_guard__raw_trace_retained=True,
        trace_integrity_guard__raw_state_retained=True,
        trace_integrity_guard__private_payload_redacted=False,
        trace_integrity_guard__operator_review_required=False,
        trace_integrity_guard__adapter_gap_review_required=False,
        trace_integrity_guard__retention_policy_ref="",
    )

    errors = validator.validate_sccml_trace_adapter_witness_record(mutated)

    assert any("authority_boundary.raw_trace_stored" in error for error in errors)
    assert any("authority_boundary.raw_state_stored" in error for error in errors)
    assert any("authority_boundary.raw_secret_value_stored" in error for error in errors)
    assert any("trace_integrity_guard.raw_trace_retained" in error for error in errors)
    assert any("trace_integrity_guard.raw_state_retained" in error for error in errors)
    assert any("private_payload_redacted" in error for error in errors)
    assert any("operator_review_required" in error for error in errors)
    assert any("adapter_gap_review_required" in error for error in errors)


def test_sccml_trace_adapter_witness_rejects_digest_and_scope_drift() -> None:
    mutated = validator.build_mutated_sccml_trace_adapter_witness(
        trace_scope__instruction_trace_ref="https://example.com/raw-trace",
        trace_scope__pre_state_hash_ref="state://raw-pre",
        trace_scope__post_state_hash_ref="file://state.json",
        trace_scope__proof_ref="proof://raw",
        trace_artifacts__adapter_manifest_ref="manifest://raw",
        trace_scope__source_kernel_family="other-kernel",
        trace_scope__adapter_mode="witness_only_digest_replay",
        trace_scope__tenant_scope="public",
        trace_scope__life_meaning_judgment_ref="schemas/other.schema.json",
    )

    errors = validator.validate_sccml_trace_adapter_witness_record(mutated)

    assert any("instruction_trace_ref must use hash://sha256/" in error for error in errors)
    assert any("instruction_trace_ref must not store raw trace URL" in error for error in errors)
    assert any("pre_state_hash_ref must use hash://sha256/" in error for error in errors)
    assert any("post_state_hash_ref must use hash://sha256/" in error for error in errors)
    assert any("proof_ref must use hash://sha256/" in error for error in errors)
    assert any("adapter_manifest_ref must use hash://sha256/" in error for error in errors)
    assert any("source_kernel_family" in error for error in errors)
    assert any("adapter_mode" in error for error in errors)
    assert any("tenant_scope" in error for error in errors)


def test_sccml_trace_adapter_witness_rejects_receipt_ref_and_count_drift() -> None:
    mutated = validator.build_mutated_sccml_trace_adapter_witness(
        receipt_refs__sccml_trace_adapter_witness_schema="schemas/other.schema.json",
        receipt_refs__kernel_proof_schema="schemas/other_kernel.schema.json",
        receipt_refs__trace_entry_schema="schemas/other_trace.schema.json",
        contract_summary__witness_only=False,
        contract_summary__kernel_authority_denied=False,
        contract_summary__authority_denial_count=1,
        contract_summary__integrity_guard_count=1,
        contract_summary__receipt_ref_count=1,
        contract_summary__evidence_ref_count=1,
        evidence_refs=["schemas/sccml_trace_adapter_witness.schema.json"],
    )

    errors = validator.validate_sccml_trace_adapter_witness_record(mutated)

    assert any("receipt_refs.sccml_trace_adapter_witness_schema" in error for error in errors)
    assert any("receipt_refs.kernel_proof_schema" in error for error in errors)
    assert any("receipt_refs.trace_entry_schema" in error for error in errors)
    assert any("contract_summary.witness_only" in error for error in errors)
    assert any("contract_summary.kernel_authority_denied" in error for error in errors)
    assert any("contract_summary.authority_denial_count" in error for error in errors)
    assert any("contract_summary.receipt_ref_count" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/sccml_trace_adapter_witness.schema.json",
            "--witness",
            "examples/sccml_trace_adapter_witness.foundation.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["schema_path"]).as_posix() == "schemas/sccml_trace_adapter_witness.schema.json"
    assert Path(payload["witness_path"]).as_posix() == "examples/sccml_trace_adapter_witness.foundation.json"
    assert payload["errors"] == []


def test_malformed_sccml_trace_adapter_witness_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_sccml_trace_adapter_witness_record(None, schema)
    list_errors = validator.validate_sccml_trace_adapter_witness_record([], schema)

    assert any("sccml trace adapter witness must be a JSON object" in error for error in none_errors)
    assert any("sccml trace adapter witness must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_sccml_trace_adapter_witness() -> None:
    requirement_path = Path("examples/sdlc/requirement_sccml_trace_adapter_witness_20260616.json")
    design_path = Path("examples/sdlc/design_sccml_trace_adapter_witness_20260616.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "sccml trace adapter witness requirement")
    design = sdlc_validator.load_json_object(design_path, "sccml trace adapter witness design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/sccml_trace_adapter_witness.schema.json" in requirement["affected_surfaces"]
    assert "schemas/sccml_trace_adapter_witness.schema.json" in design["schema_changes"]
    assert "scripts/validate_sccml_trace_adapter_witness.py" in design["validator_changes"]
    assert "tests/test_validate_sccml_trace_adapter_witness.py" in design["validator_changes"]
    assert "no live kernel execution" in requirement["non_goals"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True

"""Purpose: verify InvariantFuzzExecutionReport validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_invariant_fuzz_execution_report and SDLC validator.
Invariants:
  - Invariant fuzz evidence remains deterministic dry-run evidence.
  - Foundation Mode does not grant runtime execution, staging or production
    targeting, canonical mutation, event-chain mutation, connector, secret,
    write, rollback, terminal, or success authority.
  - Projection leaks, raw case payloads, and secret material are rejected.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_invariant_fuzz_execution_report as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_invariant_fuzz_execution_report_passes() -> None:
    errors = validator.validate_invariant_fuzz_execution_report()
    report = validator.load_json_object(validator.DEFAULT_REPORT_PATH, "InvariantFuzzExecutionReport")

    assert errors == []
    assert report["report_version"] == validator.EXPECTED_REPORT_VERSION
    assert report["fuzz_scope"]["source_family"] == "external/nested-mind-platform"
    assert report["fuzz_scope"]["foundation_mode"] is True
    assert report["harness_mode"]["mode"] == "deterministic_dry_run"
    assert report["harness_mode"]["strict_baseline_required"] is True
    assert report["harness_mode"]["projection_redaction_required"] is True
    assert report["authority_boundary"]["canonical_state_mutation_performed"] is False
    assert report["authority_boundary"]["event_chain_mutation_performed"] is False
    assert report["execution_results"]["projection_leak_detected"] is False
    assert report["safety_guards"]["raw_case_payload_retained"] is False
    assert validator.validate_invariant_fuzz_execution_report_record(report) == []


def test_invariant_fuzz_execution_report_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_invariant_fuzz_execution_report(
        authority_boundary__live_runtime_execution_performed=True,
        authority_boundary__production_target_touched=True,
        authority_boundary__staging_cluster_touched=True,
        authority_boundary__canonical_state_mutation_performed=True,
        authority_boundary__event_chain_mutation_performed=True,
        authority_boundary__lawbook_runtime_migration_performed=True,
        authority_boundary__external_connector_called=True,
        authority_boundary__secret_access_performed=True,
        authority_boundary__filesystem_write_performed=True,
        authority_boundary__rollback_executed=True,
        authority_boundary__terminal_closure_allowed=True,
        authority_boundary__success_claim_allowed=True,
    )

    errors = validator.validate_invariant_fuzz_execution_report_record(mutated)

    assert any("authority_boundary.live_runtime_execution_performed" in error for error in errors)
    assert any("authority_boundary.production_target_touched" in error for error in errors)
    assert any("authority_boundary.staging_cluster_touched" in error for error in errors)
    assert any("authority_boundary.canonical_state_mutation_performed" in error for error in errors)
    assert any("authority_boundary.event_chain_mutation_performed" in error for error in errors)
    assert any("authority_boundary.lawbook_runtime_migration_performed" in error for error in errors)
    assert any("authority_boundary.rollback_executed" in error for error in errors)
    assert any("authority_boundary.terminal_closure_allowed" in error for error in errors)


def test_invariant_fuzz_execution_report_rejects_live_scope_drift() -> None:
    mutated = validator.build_mutated_invariant_fuzz_execution_report(
        fuzz_scope__source_family="other-source",
        fuzz_scope__borrowed_concept="runtime-fuzz",
        fuzz_scope__foundation_mode=False,
        fuzz_scope__tenant_scope="production",
        harness_mode__production_target_allowed=True,
        harness_mode__staging_target_allowed=True,
        harness_mode__runtime_target_ref="https://api.mullusi.com",
    )

    errors = validator.validate_invariant_fuzz_execution_report_record(mutated)

    assert any("source_family" in error for error in errors)
    assert any("borrowed_concept" in error for error in errors)
    assert any("foundation_mode" in error for error in errors)
    assert any("tenant_scope" in error for error in errors)
    assert any("production_target_allowed" in error for error in errors)
    assert any("staging_target_allowed" in error for error in errors)
    assert any("runtime_target_ref must use none://" in error for error in errors)


def test_invariant_fuzz_execution_report_rejects_case_bank_and_oracle_drift() -> None:
    mutated = validator.build_mutated_invariant_fuzz_execution_report(
        case_bank__mutation_class_refs=["mutation://empty_patch", "mutation://empty_patch"],
        case_bank__oracle_refs=[],
        case_bank__declared_case_count=99,
        case_bank__expected_accept_count=2,
        case_bank__expected_reject_count=2,
        case_bank__projection_probe_count=0,
        safety_guards__case_bank_hash_required=False,
        safety_guards__deterministic_seed_required=False,
        safety_guards__oracle_refs_required=False,
        safety_guards__expected_accept_reject_declared=False,
    )

    errors = validator.validate_invariant_fuzz_execution_report_record(mutated)

    assert any("mutation_class_refs must not contain duplicates" in error for error in errors)
    assert any("case_bank.oracle_refs" in error for error in errors)
    assert any("declared_case_count" in error for error in errors)
    assert any("expected accept and reject counts" in error for error in errors)
    assert any("projection_probe_count" in error for error in errors)
    assert any("safety_guards.case_bank_hash_required" in error for error in errors)
    assert any("safety_guards.deterministic_seed_required" in error for error in errors)
    assert any("safety_guards.oracle_refs_required" in error for error in errors)


def test_invariant_fuzz_execution_report_rejects_projection_and_raw_retention_drift() -> None:
    mutated = validator.build_mutated_invariant_fuzz_execution_report(
        case_bank__case_bank_hash_ref="file://raw-case-bank.json",
        execution_results__result_bank_hash_ref="https://example.com/raw-results",
        execution_results__projection_leak_detected=True,
        execution_results__public_projection_checked=False,
        safety_guards__projection_leak_check_required=False,
        safety_guards__raw_case_payload_retained=True,
        safety_guards__raw_secret_material_retained=True,
    )

    errors = validator.validate_invariant_fuzz_execution_report_record(mutated)

    assert any("case_bank.case_bank_hash_ref must use hash://sha256/" in error for error in errors)
    assert any("case_bank.case_bank_hash_ref must not store raw runtime URL" in error for error in errors)
    assert any("execution_results.result_bank_hash_ref must use hash://sha256/" in error for error in errors)
    assert any("execution_results.result_bank_hash_ref must not store raw runtime URL" in error for error in errors)
    assert any("execution_results.projection_leak_detected" in error for error in errors)
    assert any("execution_results.public_projection_checked" in error for error in errors)
    assert any("safety_guards.projection_leak_check_required" in error for error in errors)
    assert any("safety_guards.raw_case_payload_retained" in error for error in errors)


def test_invariant_fuzz_execution_report_rejects_result_and_summary_count_drift() -> None:
    mutated = validator.build_mutated_invariant_fuzz_execution_report(
        execution_results__cases_executed_count=8,
        execution_results__cases_passed_count=9,
        execution_results__cases_failed_count=9,
        execution_results__unexpected_accept_count=1,
        execution_results__unexpected_reject_count=1,
        contract_summary__dry_run_only=False,
        contract_summary__canonical_mutation_denied=False,
        contract_summary__mutation_class_count=1,
        contract_summary__authority_denial_count=1,
        contract_summary__safety_guard_count=1,
    )

    errors = validator.validate_invariant_fuzz_execution_report_record(mutated)

    assert any("cases_executed_count" in error for error in errors)
    assert any("cases_passed_count" in error for error in errors)
    assert any("passed and failed counts" in error for error in errors)
    assert any("unexpected_accept_count" in error for error in errors)
    assert any("unexpected_reject_count" in error for error in errors)
    assert any("contract_summary.dry_run_only" in error for error in errors)
    assert any("contract_summary.canonical_mutation_denied" in error for error in errors)
    assert any("contract_summary.authority_denial_count" in error for error in errors)


def test_invariant_fuzz_execution_report_rejects_receipt_ref_and_count_drift() -> None:
    mutated = validator.build_mutated_invariant_fuzz_execution_report(
        receipt_refs__invariant_fuzz_execution_report_schema="schemas/other.schema.json",
        receipt_refs__universal_action_orchestration_schema="schemas/other_uao.schema.json",
        receipt_refs__life_meaning_judgment_schema="schemas/other_life.schema.json",
        contract_summary__receipt_ref_count=1,
        contract_summary__evidence_ref_count=2,
        evidence_refs=["schemas/invariant_fuzz_execution_report.schema.json"],
    )

    errors = validator.validate_invariant_fuzz_execution_report_record(mutated)

    assert any("receipt_refs.invariant_fuzz_execution_report_schema" in error for error in errors)
    assert any("receipt_refs.universal_action_orchestration_schema" in error for error in errors)
    assert any("receipt_refs.life_meaning_judgment_schema" in error for error in errors)
    assert any("contract_summary.receipt_ref_count" in error for error in errors)
    assert any("contract_summary.evidence_ref_count" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/invariant_fuzz_execution_report.schema.json",
            "--report",
            "examples/invariant_fuzz_execution_report.foundation.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["schema_path"]).as_posix() == "schemas/invariant_fuzz_execution_report.schema.json"
    assert Path(payload["report_path"]).as_posix() == "examples/invariant_fuzz_execution_report.foundation.json"
    assert payload["errors"] == []


def test_malformed_invariant_fuzz_execution_report_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_invariant_fuzz_execution_report_record(None, schema)
    list_errors = validator.validate_invariant_fuzz_execution_report_record([], schema)

    assert any("invariant fuzz execution report must be a JSON object" in error for error in none_errors)
    assert any("invariant fuzz execution report must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_invariant_fuzz_execution_report() -> None:
    requirement_path = Path("examples/sdlc/requirement_invariant_fuzz_execution_report_20260617.json")
    design_path = Path("examples/sdlc/design_invariant_fuzz_execution_report_20260617.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "invariant fuzz requirement")
    design = sdlc_validator.load_json_object(design_path, "invariant fuzz design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/invariant_fuzz_execution_report.schema.json" in requirement["affected_surfaces"]
    assert "schemas/invariant_fuzz_execution_report.schema.json" in design["schema_changes"]
    assert "scripts/validate_invariant_fuzz_execution_report.py" in design["validator_changes"]
    assert "tests/test_validate_invariant_fuzz_execution_report.py" in design["validator_changes"]
    assert "no canonical runtime mutation" in requirement["non_goals"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True

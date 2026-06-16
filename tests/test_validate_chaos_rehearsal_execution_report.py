"""Purpose: verify ChaosRehearsalExecutionReport validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_chaos_rehearsal_execution_report and SDLC validator.
Invariants:
  - Chaos rehearsal evidence remains plan-only or deterministic-dry-run.
  - Foundation Mode does not grant runtime disruption, staging or production
    targeting, event-chain mutation, connector, secret, write, rollback,
    terminal, or success authority.
  - Raw runtime logs and secret material are not retained.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_chaos_rehearsal_execution_report as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_chaos_rehearsal_execution_report_passes() -> None:
    errors = validator.validate_chaos_rehearsal_execution_report()
    report = validator.load_json_object(validator.DEFAULT_REPORT_PATH, "ChaosRehearsalExecutionReport")

    assert errors == []
    assert report["report_version"] == validator.EXPECTED_REPORT_VERSION
    assert report["rehearsal_scope"]["source_family"] == "external/nested-mind-platform"
    assert report["rehearsal_scope"]["foundation_mode"] is True
    assert report["execution_mode"]["mode"] == "deterministic_dry_run"
    assert report["execution_mode"]["production_target_allowed"] is False
    assert report["authority_boundary"]["runtime_disruption_performed"] is False
    assert report["authority_boundary"]["event_chain_mutation_performed"] is False
    assert report["safety_guards"]["rollback_obligations_declared"] is True
    assert report["safety_guards"]["raw_runtime_logs_retained"] is False
    assert validator.validate_chaos_rehearsal_execution_report_record(report) == []


def test_chaos_rehearsal_execution_report_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_chaos_rehearsal_execution_report(
        authority_boundary__live_chaos_execution_performed=True,
        authority_boundary__production_target_touched=True,
        authority_boundary__staging_cluster_touched=True,
        authority_boundary__runtime_disruption_performed=True,
        authority_boundary__network_fault_injected=True,
        authority_boundary__service_restart_performed=True,
        authority_boundary__data_corruption_performed=True,
        authority_boundary__event_chain_mutation_performed=True,
        authority_boundary__external_connector_called=True,
        authority_boundary__secret_access_performed=True,
        authority_boundary__filesystem_write_performed=True,
        authority_boundary__rollback_executed=True,
        authority_boundary__terminal_closure_allowed=True,
        authority_boundary__success_claim_allowed=True,
    )

    errors = validator.validate_chaos_rehearsal_execution_report_record(mutated)

    assert any("authority_boundary.live_chaos_execution_performed" in error for error in errors)
    assert any("authority_boundary.production_target_touched" in error for error in errors)
    assert any("authority_boundary.staging_cluster_touched" in error for error in errors)
    assert any("authority_boundary.runtime_disruption_performed" in error for error in errors)
    assert any("authority_boundary.event_chain_mutation_performed" in error for error in errors)
    assert any("authority_boundary.external_connector_called" in error for error in errors)
    assert any("authority_boundary.rollback_executed" in error for error in errors)
    assert any("authority_boundary.terminal_closure_allowed" in error for error in errors)


def test_chaos_rehearsal_execution_report_rejects_live_scope_drift() -> None:
    mutated = validator.build_mutated_chaos_rehearsal_execution_report(
        rehearsal_scope__source_family="other-source",
        rehearsal_scope__borrowed_concept="live-chaos",
        rehearsal_scope__foundation_mode=False,
        rehearsal_scope__tenant_scope="production",
        execution_mode__production_target_allowed=True,
        execution_mode__staging_target_allowed=True,
        execution_mode__destructive_injection_allowed=True,
        execution_mode__runtime_target_ref="https://api.mullusi.com",
    )

    errors = validator.validate_chaos_rehearsal_execution_report_record(mutated)

    assert any("source_family" in error for error in errors)
    assert any("borrowed_concept" in error for error in errors)
    assert any("foundation_mode" in error for error in errors)
    assert any("tenant_scope" in error for error in errors)
    assert any("production_target_allowed" in error for error in errors)
    assert any("staging_target_allowed" in error for error in errors)
    assert any("destructive_injection_allowed" in error for error in errors)
    assert any("runtime_target_ref must use none://" in error for error in errors)


def test_chaos_rehearsal_execution_report_rejects_missing_scenario_evidence_and_rollback_refs() -> None:
    mutated = validator.build_mutated_chaos_rehearsal_execution_report(
        scenario_plan__scenario_refs=[],
        scenario_plan__invariant_refs=["invariant://one", "invariant://one"],
        scenario_plan__injection_point_refs=[],
        scenario_plan__required_evidence_refs=[],
        scenario_plan__rollback_guard_refs=[],
        safety_guards__required_evidence_declared=False,
        safety_guards__rollback_obligations_declared=False,
        safety_guards__containment_expected=False,
        safety_guards__operator_review_required=False,
        safety_guards__incident_handoff_required_if_live=False,
    )

    errors = validator.validate_chaos_rehearsal_execution_report_record(mutated)

    assert any("scenario_plan.scenario_refs" in error for error in errors)
    assert any("scenario_plan.invariant_refs must not contain duplicates" in error for error in errors)
    assert any("scenario_plan.injection_point_refs" in error for error in errors)
    assert any("scenario_plan.required_evidence_refs" in error for error in errors)
    assert any("scenario_plan.rollback_guard_refs" in error for error in errors)
    assert any("safety_guards.required_evidence_declared" in error for error in errors)
    assert any("safety_guards.rollback_obligations_declared" in error for error in errors)
    assert any("safety_guards.incident_handoff_required_if_live" in error for error in errors)


def test_chaos_rehearsal_execution_report_rejects_raw_runtime_log_retention() -> None:
    mutated = validator.build_mutated_chaos_rehearsal_execution_report(
        scenario_plan__plan_hash_ref="file://raw-plan.json",
        execution_results__result_bank_hash_ref="https://example.com/raw-results",
        safety_guards__scenario_hashes_required=False,
        safety_guards__raw_runtime_logs_retained=True,
        safety_guards__raw_secret_material_retained=True,
    )

    errors = validator.validate_chaos_rehearsal_execution_report_record(mutated)

    assert any("scenario_plan.plan_hash_ref must use hash://sha256/" in error for error in errors)
    assert any("scenario_plan.plan_hash_ref must not store raw runtime URL" in error for error in errors)
    assert any("execution_results.result_bank_hash_ref must use hash://sha256/" in error for error in errors)
    assert any("execution_results.result_bank_hash_ref must not store raw runtime URL" in error for error in errors)
    assert any("safety_guards.scenario_hashes_required" in error for error in errors)
    assert any("safety_guards.raw_runtime_logs_retained" in error for error in errors)
    assert any("safety_guards.raw_secret_material_retained" in error for error in errors)


def test_chaos_rehearsal_execution_report_rejects_result_and_summary_count_drift() -> None:
    mutated = validator.build_mutated_chaos_rehearsal_execution_report(
        execution_results__scenarios_declared_count=2,
        execution_results__scenarios_executed_count=4,
        execution_results__scenarios_passed_count=5,
        execution_results__unexpected_accept_count=1,
        execution_results__unexpected_reject_count=1,
        execution_results__containment_verified=False,
        contract_summary__dry_run_only=False,
        contract_summary__runtime_disruption_denied=False,
        contract_summary__scenario_ref_count=1,
        contract_summary__authority_denial_count=1,
        contract_summary__safety_guard_count=1,
    )

    errors = validator.validate_chaos_rehearsal_execution_report_record(mutated)

    assert any("scenarios_declared_count" in error for error in errors)
    assert any("scenarios_executed_count" in error for error in errors)
    assert any("scenarios_passed_count" in error for error in errors)
    assert any("unexpected_accept_count" in error for error in errors)
    assert any("unexpected_reject_count" in error for error in errors)
    assert any("containment_verified" in error for error in errors)
    assert any("contract_summary.dry_run_only" in error for error in errors)
    assert any("contract_summary.authority_denial_count" in error for error in errors)


def test_chaos_rehearsal_execution_report_rejects_receipt_ref_and_count_drift() -> None:
    mutated = validator.build_mutated_chaos_rehearsal_execution_report(
        receipt_refs__chaos_rehearsal_execution_report_schema="schemas/other.schema.json",
        receipt_refs__universal_action_orchestration_schema="schemas/other_uao.schema.json",
        receipt_refs__life_meaning_judgment_schema="schemas/other_life.schema.json",
        contract_summary__receipt_ref_count=1,
        contract_summary__evidence_ref_count=2,
        evidence_refs=["schemas/chaos_rehearsal_execution_report.schema.json"],
    )

    errors = validator.validate_chaos_rehearsal_execution_report_record(mutated)

    assert any("receipt_refs.chaos_rehearsal_execution_report_schema" in error for error in errors)
    assert any("receipt_refs.universal_action_orchestration_schema" in error for error in errors)
    assert any("receipt_refs.life_meaning_judgment_schema" in error for error in errors)
    assert any("contract_summary.receipt_ref_count" in error for error in errors)
    assert any("contract_summary.evidence_ref_count" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/chaos_rehearsal_execution_report.schema.json",
            "--report",
            "examples/chaos_rehearsal_execution_report.foundation.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["schema_path"]).as_posix() == "schemas/chaos_rehearsal_execution_report.schema.json"
    assert Path(payload["report_path"]).as_posix() == "examples/chaos_rehearsal_execution_report.foundation.json"
    assert payload["errors"] == []


def test_malformed_chaos_rehearsal_execution_report_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_chaos_rehearsal_execution_report_record(None, schema)
    list_errors = validator.validate_chaos_rehearsal_execution_report_record([], schema)

    assert any("chaos rehearsal execution report must be a JSON object" in error for error in none_errors)
    assert any("chaos rehearsal execution report must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_chaos_rehearsal_execution_report() -> None:
    requirement_path = Path("examples/sdlc/requirement_chaos_rehearsal_execution_report_20260616.json")
    design_path = Path("examples/sdlc/design_chaos_rehearsal_execution_report_20260616.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "chaos rehearsal requirement")
    design = sdlc_validator.load_json_object(design_path, "chaos rehearsal design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/chaos_rehearsal_execution_report.schema.json" in requirement["affected_surfaces"]
    assert "schemas/chaos_rehearsal_execution_report.schema.json" in design["schema_changes"]
    assert "scripts/validate_chaos_rehearsal_execution_report.py" in design["validator_changes"]
    assert "tests/test_validate_chaos_rehearsal_execution_report.py" in design["validator_changes"]
    assert "no live chaos execution" in requirement["non_goals"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True

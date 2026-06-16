"""Purpose: verify dry-run resilience rehearsal report validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_resilience_rehearsal_reports and SDLC validator.
Invariants:
  - Chaos rehearsal reports are non-executing in Foundation Mode.
  - Invariant fuzz reports use deterministic fixtures only in Foundation Mode.
  - Production-readiness, success, and terminal closure remain denied.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_resilience_rehearsal_reports as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_resilience_rehearsal_reports_pass() -> None:
    errors = validator.validate_resilience_rehearsal_reports()
    chaos = validator.load_json_object(validator.CHAOS_REPORT_PATH, "ChaosRehearsalExecutionReport")
    fuzz = validator.load_json_object(validator.FUZZ_REPORT_PATH, "InvariantFuzzExecutionReport")

    assert errors == []
    assert chaos["report_version"] == validator.EXPECTED_CHAOS_VERSION
    assert fuzz["report_version"] == validator.EXPECTED_FUZZ_VERSION
    assert chaos["rehearsal_scope"]["execution_mode"] == "dry_run"
    assert fuzz["fuzz_scope"]["seed_policy"] == "deterministic_fixture_only"
    assert chaos["rehearsal_result"]["runtime_execution_performed"] is False
    assert fuzz["fuzz_result"]["cases_executed"] == 0
    assert validator.validate_chaos_rehearsal_execution_report_record(chaos) == []
    assert validator.validate_invariant_fuzz_execution_report_record(fuzz) == []


def test_chaos_rehearsal_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_chaos_rehearsal_execution_report(
        rehearsal_scope__execution_mode="live_runtime",
        rehearsal_scope__phi_gov_ref="phi-gov://authorized",
        rehearsal_result__decision="CHAOS_REHEARSAL_EXECUTED",
        rehearsal_result__runtime_execution_performed=True,
        rehearsal_result__external_effects_performed=True,
        rehearsal_result__filesystem_mutation_performed=True,
        rehearsal_result__deployment_mutation_allowed=True,
        rehearsal_result__production_readiness_claim_allowed=True,
        rehearsal_result__terminal_closure_allowed=True,
        rehearsal_result__success_claim_allowed=True,
    )

    errors = validator.validate_chaos_rehearsal_execution_report_record(mutated)

    assert any("rehearsal_scope.execution_mode" in error for error in errors)
    assert any("rehearsal_scope.phi_gov_ref" in error for error in errors)
    assert any("rehearsal_result.decision" in error for error in errors)
    assert any("runtime_execution_performed" in error for error in errors)
    assert any("deployment_mutation_allowed" in error for error in errors)
    assert any("terminal_closure_allowed" in error for error in errors)


def test_invariant_fuzz_rejects_execution_and_random_generation() -> None:
    mutated = validator.build_mutated_invariant_fuzz_execution_report(
        fuzz_scope__execution_mode="live_runtime",
        fuzz_scope__seed_policy="random_live_generation",
        fuzz_scope__phi_gov_ref="phi-gov://authorized",
        fuzz_result__decision="INVARIANT_FUZZ_EXECUTED",
        fuzz_result__cases_executed=2,
        fuzz_result__random_generation_performed=True,
        fuzz_result__runtime_execution_performed=True,
        fuzz_result__external_effects_performed=True,
        fuzz_result__filesystem_mutation_performed=True,
        fuzz_result__production_readiness_claim_allowed=True,
        fuzz_result__terminal_closure_allowed=True,
        fuzz_result__success_claim_allowed=True,
        contract_summary__cases_executed=2,
    )

    errors = validator.validate_invariant_fuzz_execution_report_record(mutated)

    assert any("fuzz_scope.execution_mode" in error for error in errors)
    assert any("fuzz_scope.seed_policy" in error for error in errors)
    assert any("fuzz_scope.phi_gov_ref" in error for error in errors)
    assert any("fuzz_result.decision" in error for error in errors)
    assert any("fuzz_result.cases_executed" in error for error in errors)
    assert any("random_generation_performed" in error for error in errors)
    assert any("contract_summary.cases_executed" in error for error in errors)


def test_resilience_rehearsal_reports_reject_missing_refs() -> None:
    chaos = validator.build_mutated_chaos_rehearsal_execution_report(
        rehearsal_result__required_evidence_refs=["evidence://chaos-rehearsal/operator-approval"],
        rehearsal_result__blocked_reason_refs=["blocked://chaos-rehearsal/runtime-sandbox-missing"],
        evidence_refs=["schemas/chaos_rehearsal_execution_report.schema.json"],
    )
    fuzz = validator.build_mutated_invariant_fuzz_execution_report(
        fuzz_result__required_evidence_refs=["evidence://invariant-fuzz/operator-approval"],
        fuzz_result__blocked_reason_refs=["blocked://invariant-fuzz/runtime-sandbox-missing"],
        evidence_refs=["schemas/invariant_fuzz_execution_report.schema.json"],
    )

    chaos_errors = validator.validate_chaos_rehearsal_execution_report_record(chaos)
    fuzz_errors = validator.validate_invariant_fuzz_execution_report_record(fuzz)

    assert any("required_evidence_refs missing required ref" in error for error in chaos_errors)
    assert any("blocked_reason_refs missing required ref" in error for error in chaos_errors)
    assert any("evidence_refs missing required ref" in error for error in chaos_errors)
    assert any("required_evidence_refs missing required ref" in error for error in fuzz_errors)
    assert any("blocked_reason_refs missing required ref" in error for error in fuzz_errors)
    assert any("evidence_refs missing required ref" in error for error in fuzz_errors)


def test_resilience_rehearsal_reports_reject_obligation_and_count_drift() -> None:
    chaos = validator.build_mutated_chaos_rehearsal_execution_report(
        contract_summary__scenario_count=1,
        contract_summary__required_evidence_ref_count=1,
        contract_summary__blocked_reason_ref_count=1,
        contract_summary__receipt_ref_count=1,
        contract_summary__evidence_ref_count=1,
    )
    chaos["scenarios"][0]["scenario_id"] = chaos["scenarios"][1]["scenario_id"]
    chaos["scenarios"][0]["observed_result"] = "executed"
    chaos["scenarios"][0]["rollback_obligation_ref"] = ""
    fuzz = validator.build_mutated_invariant_fuzz_execution_report(contract_summary__case_count=1)
    fuzz["cases"][0]["case_id"] = fuzz["cases"][1]["case_id"]
    fuzz["cases"][0]["observed_result"] = "executed"
    fuzz["cases"][0]["incident_handoff_ref"] = ""

    chaos_errors = validator.validate_chaos_rehearsal_execution_report_record(chaos)
    fuzz_errors = validator.validate_invariant_fuzz_execution_report_record(fuzz)

    assert any("scenarios[0].observed_result" in error for error in chaos_errors)
    assert any("scenarios[0].rollback_obligation_ref" in error for error in chaos_errors)
    assert any("scenarios[1].scenario_id must be unique" in error for error in chaos_errors)
    assert any("contract_summary.scenario_count" in error for error in chaos_errors)
    assert any("contract_summary.required_evidence_ref_count" in error for error in chaos_errors)
    assert any("cases[0].observed_result" in error for error in fuzz_errors)
    assert any("cases[0].incident_handoff_ref" in error for error in fuzz_errors)
    assert any("cases[1].case_id must be unique" in error for error in fuzz_errors)
    assert any("contract_summary.case_count" in error for error in fuzz_errors)


def test_resilience_rehearsal_reports_reject_rollback_and_receipt_drift() -> None:
    chaos = validator.build_mutated_chaos_rehearsal_execution_report(
        rollback_recovery__rollback_required_before_live_execution=False,
        rollback_recovery__incident_handoff_required=False,
        rollback_recovery__terminal_closure_ref="closure://terminal",
        rollback_recovery__rollback_plan_ref="",
        receipt_refs__worker_failure_receipt_schema="schemas/other.schema.json",
    )
    fuzz = validator.build_mutated_invariant_fuzz_execution_report(
        rollback_recovery__terminal_closure_ref="closure://terminal",
        rollback_recovery__replay_bundle_ref="",
        receipt_refs__life_meaning_judgment_schema="schemas/other.schema.json",
    )

    chaos_errors = validator.validate_chaos_rehearsal_execution_report_record(chaos)
    fuzz_errors = validator.validate_invariant_fuzz_execution_report_record(fuzz)

    assert any("rollback_required_before_live_execution" in error for error in chaos_errors)
    assert any("incident_handoff_required" in error for error in chaos_errors)
    assert any("terminal_closure_ref" in error for error in chaos_errors)
    assert any("rollback_plan_ref" in error for error in chaos_errors)
    assert any("receipt_refs.worker_failure_receipt_schema" in error for error in chaos_errors)
    assert any("terminal_closure_ref" in error for error in fuzz_errors)
    assert any("replay_bundle_ref" in error for error in fuzz_errors)
    assert any("receipt_refs.life_meaning_judgment_schema" in error for error in fuzz_errors)


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--chaos-schema",
            "schemas/chaos_rehearsal_execution_report.schema.json",
            "--chaos-report",
            "examples/chaos_rehearsal_execution_report.foundation.json",
            "--fuzz-schema",
            "schemas/invariant_fuzz_execution_report.schema.json",
            "--fuzz-report",
            "examples/invariant_fuzz_execution_report.foundation.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["chaos_schema_path"]).as_posix() == "schemas/chaos_rehearsal_execution_report.schema.json"
    assert Path(payload["fuzz_schema_path"]).as_posix() == "schemas/invariant_fuzz_execution_report.schema.json"
    assert payload["errors"] == []


def test_malformed_resilience_rehearsal_reports_report_errors() -> None:
    chaos_schema = validator._load_schema(validator.CHAOS_SCHEMA_PATH)
    fuzz_schema = validator._load_schema(validator.FUZZ_SCHEMA_PATH)

    chaos_errors = validator.validate_chaos_rehearsal_execution_report_record(None, chaos_schema)
    fuzz_errors = validator.validate_invariant_fuzz_execution_report_record([], fuzz_schema)

    assert any("chaos rehearsal execution report must be a JSON object" in error for error in chaos_errors)
    assert any("invariant fuzz execution report must be a JSON object" in error for error in fuzz_errors)
    assert any("expected object" in error for error in chaos_errors + fuzz_errors)


def test_sdlc_requirement_and_design_validate_for_resilience_rehearsal_reports() -> None:
    requirement_path = Path("examples/sdlc/requirement_resilience_rehearsal_reports_20260616.json")
    design_path = Path("examples/sdlc/design_resilience_rehearsal_reports_20260616.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "resilience rehearsal reports requirement")
    design = sdlc_validator.load_json_object(design_path, "resilience rehearsal reports design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/chaos_rehearsal_execution_report.schema.json" in requirement["affected_surfaces"]
    assert "schemas/invariant_fuzz_execution_report.schema.json" in design["schema_changes"]
    assert "scripts/validate_resilience_rehearsal_reports.py" in design["validator_changes"]
    assert "tests/test_validate_resilience_rehearsal_reports.py" in design["validator_changes"]
    assert "no runtime execution" in requirement["non_goals"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True

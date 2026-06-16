#!/usr/bin/env python3
"""Validate dry-run resilience rehearsal report contracts.

Purpose: verify that chaos rehearsal and invariant fuzz report artifacts remain
bounded evidence packets instead of becoming runtime execution, deployment, or
terminal-closure authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, schema validation helpers, UAO,
worker-failure, recovery handoff, and Life-Meaning judgment schemas.
Invariants:
  - Validation is read-only and deterministic.
  - Foundation examples never execute runtime, fuzz, filesystem, connector, or
    external effects.
  - Production-readiness, terminal-closure, and success claims remain denied.
  - Rollback, replay, incident handoff, evidence refs, and blocked reasons are
    explicit.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import sys
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


CHAOS_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "chaos_rehearsal_execution_report.schema.json"
CHAOS_REPORT_PATH = WORKSPACE_ROOT / "examples" / "chaos_rehearsal_execution_report.foundation.json"
FUZZ_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "invariant_fuzz_execution_report.schema.json"
FUZZ_REPORT_PATH = WORKSPACE_ROOT / "examples" / "invariant_fuzz_execution_report.foundation.json"

EXPECTED_CHAOS_SCHEMA_ID = "urn:mullusi:schema:chaos-rehearsal-execution-report:1"
EXPECTED_CHAOS_TITLE = "Chaos Rehearsal Execution Report"
EXPECTED_CHAOS_VERSION = "chaos_rehearsal_execution_report.v1"
EXPECTED_CHAOS_DECISION = "CHAOS_REHEARSAL_DRY_RUN_BLOCKED_AWAITING_RUNTIME_EVIDENCE"
EXPECTED_FUZZ_SCHEMA_ID = "urn:mullusi:schema:invariant-fuzz-execution-report:1"
EXPECTED_FUZZ_TITLE = "Invariant Fuzz Execution Report"
EXPECTED_FUZZ_VERSION = "invariant_fuzz_execution_report.v1"
EXPECTED_FUZZ_DECISION = "INVARIANT_FUZZ_DRY_RUN_BLOCKED_AWAITING_RUNTIME_EVIDENCE"

CHAOS_REQUIRED_EVIDENCE_REFS = (
    "evidence://chaos-rehearsal/operator-approval",
    "evidence://chaos-rehearsal/runtime-sandbox",
    "evidence://chaos-rehearsal/rollback-rehearsal",
    "evidence://chaos-rehearsal/incident-handoff",
    "evidence://chaos-rehearsal/monitoring-witness",
)
CHAOS_REQUIRED_BLOCKED_REASON_REFS = (
    "blocked://chaos-rehearsal/runtime-sandbox-missing",
    "blocked://chaos-rehearsal/operator-approval-missing",
    "blocked://chaos-rehearsal/rollback-rehearsal-missing",
    "blocked://production-readiness/denied",
)
CHAOS_RECEIPT_REFS = {
    "chaos_rehearsal_execution_report_schema": "schemas/chaos_rehearsal_execution_report.schema.json",
    "universal_action_orchestration_schema": "schemas/universal_action_orchestration.schema.json",
    "worker_failure_receipt_schema": "schemas/worker_failure_receipt.schema.json",
    "sdlc_recovery_handoff_receipt_schema": "schemas/sdlc_recovery_handoff_receipt.schema.json",
}
CHAOS_ARTIFACT_REFS = (
    "schemas/chaos_rehearsal_execution_report.schema.json",
    "examples/chaos_rehearsal_execution_report.foundation.json",
    "scripts/validate_resilience_rehearsal_reports.py",
    "tests/test_validate_resilience_rehearsal_reports.py",
    "docs/87_resilience_rehearsal_reports_contract.md",
    "schemas/universal_action_orchestration.schema.json",
    "schemas/worker_failure_receipt.schema.json",
)

FUZZ_REQUIRED_EVIDENCE_REFS = (
    "evidence://invariant-fuzz/operator-approval",
    "evidence://invariant-fuzz/runtime-sandbox",
    "evidence://invariant-fuzz/deterministic-seed-manifest",
    "evidence://invariant-fuzz/rollback-rehearsal",
    "evidence://invariant-fuzz/incident-handoff",
)
FUZZ_REQUIRED_BLOCKED_REASON_REFS = (
    "blocked://invariant-fuzz/runtime-sandbox-missing",
    "blocked://invariant-fuzz/operator-approval-missing",
    "blocked://invariant-fuzz/seed-manifest-missing",
    "blocked://terminal-closure/denied",
)
FUZZ_RECEIPT_REFS = {
    "invariant_fuzz_execution_report_schema": "schemas/invariant_fuzz_execution_report.schema.json",
    "universal_action_orchestration_schema": "schemas/universal_action_orchestration.schema.json",
    "sdlc_recovery_handoff_receipt_schema": "schemas/sdlc_recovery_handoff_receipt.schema.json",
    "life_meaning_judgment_schema": "schemas/life_meaning_judgment.schema.json",
}
FUZZ_ARTIFACT_REFS = (
    "schemas/invariant_fuzz_execution_report.schema.json",
    "examples/invariant_fuzz_execution_report.foundation.json",
    "scripts/validate_resilience_rehearsal_reports.py",
    "tests/test_validate_resilience_rehearsal_reports.py",
    "docs/87_resilience_rehearsal_reports_contract.md",
    "schemas/universal_action_orchestration.schema.json",
    "schemas/sdlc_recovery_handoff_receipt.schema.json",
)


class ResilienceRehearsalReportError(ValueError):
    """Raised when a resilience rehearsal report artifact cannot load."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    path = json_path if json_path.is_absolute() else WORKSPACE_ROOT / json_path
    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ResilienceRehearsalReportError(f"{label} must be a JSON object")
    return payload


def validate_schema_artifact(schema: dict[str, Any], expected_id: str, expected_title: str) -> list[str]:
    """Return deterministic schema artifact errors."""

    errors: list[str] = []
    if schema.get("$id") != expected_id:
        errors.append(f"schema $id is invalid for {expected_title}")
    if schema.get("title") != expected_title:
        errors.append(f"schema title is invalid for {expected_title}")
    if schema.get("type") != "object":
        errors.append(f"schema root type must be object for {expected_title}")
    if schema.get("additionalProperties") is not False:
        errors.append(f"schema root must close additional properties for {expected_title}")
    required_fields = schema.get("required")
    properties = schema.get("properties")
    if not isinstance(required_fields, list):
        errors.append(f"schema required field must be a list for {expected_title}")
    if not isinstance(properties, dict):
        errors.append(f"schema properties must be an object for {expected_title}")
    if isinstance(required_fields, list) and isinstance(properties, dict):
        for field_name in (
            "report_id",
            "report_version",
            "generated_at",
            "rollback_recovery",
            "receipt_refs",
            "contract_summary",
            "evidence_refs",
        ):
            if field_name not in required_fields:
                errors.append(f"schema missing required field {field_name} for {expected_title}")
            if field_name not in properties:
                errors.append(f"schema missing property {field_name} for {expected_title}")
    return errors


def validate_chaos_rehearsal_execution_report_record(
    record: Any,
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one chaos rehearsal report."""

    schema_payload = schema or _load_schema(CHAOS_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("chaos rehearsal execution report must be a JSON object")
        return errors

    _validate_common_top_level(record, EXPECTED_CHAOS_VERSION, errors)
    scope = record.get("rehearsal_scope")
    result = record.get("rehearsal_result")
    _validate_dry_run_scope(scope, "rehearsal_scope", errors)
    _validate_denied_result(
        result,
        "rehearsal_result",
        EXPECTED_CHAOS_DECISION,
        CHAOS_REQUIRED_EVIDENCE_REFS,
        CHAOS_REQUIRED_BLOCKED_REASON_REFS,
        errors,
    )
    _validate_obligation_items(record.get("scenarios"), "scenarios", "scenario_id", errors)
    _validate_rollback_recovery(record.get("rollback_recovery"), errors)
    _validate_receipt_refs(record.get("receipt_refs"), CHAOS_RECEIPT_REFS, errors)
    _validate_common_summary(record, "scenario_count", "scenarios", errors)
    _require_subset(record, "evidence_refs", CHAOS_ARTIFACT_REFS, errors)
    return errors


def validate_invariant_fuzz_execution_report_record(
    record: Any,
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one invariant fuzz report."""

    schema_payload = schema or _load_schema(FUZZ_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("invariant fuzz execution report must be a JSON object")
        return errors

    _validate_common_top_level(record, EXPECTED_FUZZ_VERSION, errors)
    scope = record.get("fuzz_scope")
    result = record.get("fuzz_result")
    _validate_dry_run_scope(scope, "fuzz_scope", errors)
    if isinstance(scope, dict) and scope.get("seed_policy") != "deterministic_fixture_only":
        errors.append("fuzz_scope.seed_policy must remain deterministic_fixture_only")
    _validate_denied_result(
        result,
        "fuzz_result",
        EXPECTED_FUZZ_DECISION,
        FUZZ_REQUIRED_EVIDENCE_REFS,
        FUZZ_REQUIRED_BLOCKED_REASON_REFS,
        errors,
    )
    if isinstance(result, dict):
        if result.get("cases_executed") != 0:
            errors.append("fuzz_result.cases_executed must remain 0 in Foundation Mode")
        if result.get("random_generation_performed") is not False:
            errors.append("fuzz_result.random_generation_performed must remain false")
    _validate_obligation_items(record.get("cases"), "cases", "case_id", errors)
    _validate_rollback_recovery(record.get("rollback_recovery"), errors)
    _validate_receipt_refs(record.get("receipt_refs"), FUZZ_RECEIPT_REFS, errors)
    _validate_common_summary(record, "case_count", "cases", errors)
    summary = record.get("contract_summary")
    if isinstance(summary, dict) and summary.get("cases_executed") != 0:
        errors.append("contract_summary.cases_executed must remain 0")
    _require_subset(record, "evidence_refs", FUZZ_ARTIFACT_REFS, errors)
    return errors


def validate_resilience_rehearsal_reports(
    chaos_schema_path: Path = CHAOS_SCHEMA_PATH,
    chaos_report_path: Path = CHAOS_REPORT_PATH,
    fuzz_schema_path: Path = FUZZ_SCHEMA_PATH,
    fuzz_report_path: Path = FUZZ_REPORT_PATH,
) -> list[str]:
    """Validate both dry-run resilience rehearsal report contracts."""

    chaos_schema = _load_schema(chaos_schema_path)
    chaos_report = load_json_object(chaos_report_path, "ChaosRehearsalExecutionReport")
    fuzz_schema = _load_schema(fuzz_schema_path)
    fuzz_report = load_json_object(fuzz_report_path, "InvariantFuzzExecutionReport")
    errors = validate_schema_artifact(chaos_schema, EXPECTED_CHAOS_SCHEMA_ID, EXPECTED_CHAOS_TITLE)
    errors.extend(validate_schema_artifact(fuzz_schema, EXPECTED_FUZZ_SCHEMA_ID, EXPECTED_FUZZ_TITLE))
    errors.extend(validate_chaos_rehearsal_execution_report_record(chaos_report, chaos_schema))
    errors.extend(validate_invariant_fuzz_execution_report_record(fuzz_report, fuzz_schema))
    return errors


def build_mutated_chaos_rehearsal_execution_report(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default chaos report."""

    return _build_mutated_report(CHAOS_REPORT_PATH, "ChaosRehearsalExecutionReport", **updates)


def build_mutated_invariant_fuzz_execution_report(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default invariant fuzz report."""

    return _build_mutated_report(FUZZ_REPORT_PATH, "InvariantFuzzExecutionReport", **updates)


def workspace_display_path(path: Path) -> str:
    """Return a stable workspace-relative display path when possible."""

    resolved_path = path if path.is_absolute() else WORKSPACE_ROOT / path
    try:
        return str(resolved_path.resolve().relative_to(WORKSPACE_ROOT))
    except ValueError:
        return str(path)


def _build_mutated_report(report_path: Path, label: str, **updates: Any) -> dict[str, Any]:
    report = load_json_object(report_path, label)
    mutated = deepcopy(report)
    for dotted_key, value in updates.items():
        target = mutated
        segments = dotted_key.split("__")
        for segment in segments[:-1]:
            next_target = target.get(segment)
            if not isinstance(next_target, dict):
                next_target = {}
                target[segment] = next_target
            target = next_target
        target[segments[-1]] = value
    return mutated


def _validate_common_top_level(record: dict[str, Any], expected_version: str, errors: list[str]) -> None:
    if record.get("report_version") != expected_version:
        errors.append(f"report_version must match {expected_version}")
    if not isinstance(record.get("report_id"), str) or record.get("report_id") == "":
        errors.append("report_id must be non-empty")


def _validate_dry_run_scope(scope: Any, label: str, errors: list[str]) -> None:
    if not isinstance(scope, dict):
        errors.append(f"{label} must be an object")
        return
    if scope.get("execution_mode") != "dry_run":
        errors.append(f"{label}.execution_mode must remain dry_run")
    if scope.get("phi_gov_ref") is not None:
        errors.append(f"{label}.phi_gov_ref must remain absent in Foundation Mode")
    if not scope.get("uao_ref"):
        errors.append(f"{label}.uao_ref must be non-empty")


def _validate_denied_result(
    result: Any,
    label: str,
    expected_decision: str,
    required_evidence_refs: tuple[str, ...],
    required_blocked_reason_refs: tuple[str, ...],
    errors: list[str],
) -> None:
    if not isinstance(result, dict):
        errors.append(f"{label} must be an object")
        return
    if result.get("decision") != expected_decision:
        errors.append(f"{label}.decision must remain {expected_decision}")
    for field_name in (
        "runtime_execution_performed",
        "external_effects_performed",
        "filesystem_mutation_performed",
        "production_readiness_claim_allowed",
        "terminal_closure_allowed",
        "success_claim_allowed",
    ):
        if result.get(field_name) is not False:
            errors.append(f"{label}.{field_name} must remain false")
    if "deployment_mutation_allowed" in result and result.get("deployment_mutation_allowed") is not False:
        errors.append(f"{label}.deployment_mutation_allowed must remain false")
    _require_subset(result, "required_evidence_refs", required_evidence_refs, errors)
    _require_subset(result, "blocked_reason_refs", required_blocked_reason_refs, errors)


def _validate_obligation_items(items: Any, label: str, id_field: str, errors: list[str]) -> None:
    if not isinstance(items, list) or not items:
        errors.append(f"{label} must be a non-empty list")
        return
    seen_ids: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"{label}[{index}] must be an object")
            continue
        item_id = item.get(id_field)
        if not isinstance(item_id, str) or not item_id:
            errors.append(f"{label}[{index}].{id_field} must be non-empty")
        elif item_id in seen_ids:
            errors.append(f"{label}[{index}].{id_field} must be unique")
        else:
            seen_ids.add(item_id)
        if item.get("observed_result") != "not_executed_dry_run":
            errors.append(f"{label}[{index}].observed_result must remain not_executed_dry_run")
        for field_name in ("rollback_obligation_ref", "incident_handoff_ref"):
            if not item.get(field_name):
                errors.append(f"{label}[{index}].{field_name} must be non-empty")


def _validate_rollback_recovery(recovery: Any, errors: list[str]) -> None:
    if not isinstance(recovery, dict):
        errors.append("rollback_recovery must be an object")
        return
    if recovery.get("rollback_required_before_live_execution") is not True:
        errors.append("rollback_recovery.rollback_required_before_live_execution must be true")
    if recovery.get("incident_handoff_required") is not True:
        errors.append("rollback_recovery.incident_handoff_required must be true")
    if recovery.get("terminal_closure_ref") is not None:
        errors.append("rollback_recovery.terminal_closure_ref must remain absent")
    for field_name in ("rollback_plan_ref", "replay_bundle_ref"):
        if not recovery.get(field_name):
            errors.append(f"rollback_recovery.{field_name} must be non-empty")


def _validate_receipt_refs(refs: Any, expected_refs: dict[str, str], errors: list[str]) -> None:
    if not isinstance(refs, dict):
        errors.append("receipt_refs must be an object")
        return
    for key, expected_value in expected_refs.items():
        if refs.get(key) != expected_value:
            errors.append(f"receipt_refs.{key} must equal {expected_value}")


def _validate_common_summary(
    record: dict[str, Any],
    item_count_field: str,
    item_array_field: str,
    errors: list[str],
) -> None:
    summary = record.get("contract_summary")
    if not isinstance(summary, dict):
        errors.append("contract_summary must be an object")
        return
    items = record.get(item_array_field)
    if isinstance(items, list) and summary.get(item_count_field) != len(items):
        errors.append(f"contract_summary.{item_count_field} must match {item_array_field} length")
    result = record.get("rehearsal_result") or record.get("fuzz_result")
    if isinstance(result, dict):
        if summary.get("required_evidence_ref_count") != len(result.get("required_evidence_refs", [])):
            errors.append("contract_summary.required_evidence_ref_count must match required_evidence_refs length")
        if summary.get("blocked_reason_ref_count") != len(result.get("blocked_reason_refs", [])):
            errors.append("contract_summary.blocked_reason_ref_count must match blocked_reason_refs length")
    refs = record.get("receipt_refs")
    if isinstance(refs, dict) and summary.get("receipt_ref_count") != len(refs):
        errors.append("contract_summary.receipt_ref_count must match receipt_refs length")
    evidence_refs = record.get("evidence_refs")
    if isinstance(evidence_refs, list) and summary.get("evidence_ref_count") != len(evidence_refs):
        errors.append("contract_summary.evidence_ref_count must match evidence_refs length")


def _require_subset(
    record: Any,
    field_name: str,
    required_values: tuple[str, ...],
    errors: list[str],
) -> None:
    values = record.get(field_name) if isinstance(record, dict) else None
    if not isinstance(values, list):
        errors.append(f"{field_name} must be a list")
        return
    value_set = set(values)
    for required_value in required_values:
        if required_value not in value_set:
            errors.append(f"{field_name} missing required ref: {required_value}")


def main(argv: list[str] | None = None) -> int:
    """Validate resilience rehearsal reports from the CLI."""

    parser = argparse.ArgumentParser(description="Validate dry-run resilience rehearsal report contracts.")
    parser.add_argument("--chaos-schema", type=Path, default=CHAOS_SCHEMA_PATH)
    parser.add_argument("--chaos-report", type=Path, default=CHAOS_REPORT_PATH)
    parser.add_argument("--fuzz-schema", type=Path, default=FUZZ_SCHEMA_PATH)
    parser.add_argument("--fuzz-report", type=Path, default=FUZZ_REPORT_PATH)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    errors = validate_resilience_rehearsal_reports(
        args.chaos_schema,
        args.chaos_report,
        args.fuzz_schema,
        args.fuzz_report,
    )
    if args.json:
        payload = {
            "receipt_id": "resilience_rehearsal_reports_validation",
            "status": "passed" if not errors else "failed",
            "chaos_schema_path": workspace_display_path(args.chaos_schema),
            "chaos_report_path": workspace_display_path(args.chaos_report),
            "fuzz_schema_path": workspace_display_path(args.fuzz_schema),
            "fuzz_report_path": workspace_display_path(args.fuzz_report),
            "errors": errors,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif errors:
        for error in errors:
            print(f"[FAIL] {error}")
    else:
        print("[PASS] resilience_rehearsal_reports")
        print("STATUS: passed")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

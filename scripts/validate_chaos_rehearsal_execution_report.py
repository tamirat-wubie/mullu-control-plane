#!/usr/bin/env python3
"""Validate the ChaosRehearsalExecutionReport contract.

Purpose: verify that chaos rehearsal evidence remains plan-only or
deterministic-dry-run, rollback-bound, and separated from runtime disruption,
staging or production targets, raw log retention, and terminal authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, schema validation helpers, UAO,
LifeMeaningJudgment, EffectAssurance, SimulationReceipt, WorkerFailureReceipt,
and SDLC recovery handoff schemas.
Invariants:
  - Validation is read-only and deterministic.
  - The Foundation example performs no live chaos execution.
  - Runtime disruption, staging/production targets, event-chain mutation,
    connector calls, secret access, filesystem writes, rollback execution,
    terminal closure, success claims, raw runtime logs, and raw secrets remain
    denied.
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


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "chaos_rehearsal_execution_report.schema.json"
DEFAULT_REPORT_PATH = WORKSPACE_ROOT / "examples" / "chaos_rehearsal_execution_report.foundation.json"

EXPECTED_SCHEMA_ID = "urn:mullusi:schema:chaos-rehearsal-execution-report:1"
EXPECTED_SCHEMA_TITLE = "Chaos Rehearsal Execution Report"
EXPECTED_REPORT_VERSION = "chaos_rehearsal_execution_report.v1"
REQUIRED_RECEIPT_REFS = {
    "chaos_rehearsal_execution_report_schema": "schemas/chaos_rehearsal_execution_report.schema.json",
    "universal_action_orchestration_schema": "schemas/universal_action_orchestration.schema.json",
    "life_meaning_judgment_schema": "schemas/life_meaning_judgment.schema.json",
    "effect_assurance_schema": "schemas/effect_assurance.schema.json",
    "simulation_receipt_schema": "schemas/simulation_receipt.schema.json",
    "worker_failure_receipt_schema": "schemas/worker_failure_receipt.schema.json",
    "sdlc_recovery_handoff_receipt_schema": "schemas/sdlc_recovery_handoff_receipt.schema.json",
}
REQUIRED_ARTIFACT_REFS = (
    "schemas/chaos_rehearsal_execution_report.schema.json",
    "examples/chaos_rehearsal_execution_report.foundation.json",
    "scripts/validate_chaos_rehearsal_execution_report.py",
    "tests/test_validate_chaos_rehearsal_execution_report.py",
    "docs/91_chaos_rehearsal_execution_report_contract.md",
    "docs/82_cross_repo_opportunity_map.md",
    "schemas/universal_action_orchestration.schema.json",
    "schemas/life_meaning_judgment.schema.json",
    "schemas/effect_assurance.schema.json",
    "schemas/simulation_receipt.schema.json",
    "schemas/sdlc_recovery_handoff_receipt.schema.json",
)
DENIED_AUTHORITY_FIELDS = (
    "live_chaos_execution_performed",
    "production_target_touched",
    "staging_cluster_touched",
    "runtime_disruption_performed",
    "network_fault_injected",
    "service_restart_performed",
    "data_corruption_performed",
    "event_chain_mutation_performed",
    "external_connector_called",
    "secret_access_performed",
    "filesystem_write_performed",
    "rollback_executed",
    "terminal_closure_allowed",
    "success_claim_allowed",
)
REQUIRED_TRUE_GUARD_FIELDS = (
    "scenario_hashes_required",
    "required_evidence_declared",
    "rollback_obligations_declared",
    "containment_expected",
    "operator_review_required",
    "incident_handoff_required_if_live",
)
REQUIRED_FALSE_GUARD_FIELDS = (
    "raw_runtime_logs_retained",
    "raw_secret_material_retained",
)
DIGEST_REF_FIELDS = (
    ("scenario_plan", "plan_hash_ref"),
    ("execution_results", "result_bank_hash_ref"),
)


class ChaosRehearsalExecutionReportError(ValueError):
    """Raised when a ChaosRehearsalExecutionReport artifact cannot load."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    path = json_path if json_path.is_absolute() else WORKSPACE_ROOT / json_path
    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ChaosRehearsalExecutionReportError(f"{label} must be a JSON object")
    return payload


def validate_schema_artifact(schema: dict[str, Any]) -> list[str]:
    """Return deterministic schema artifact errors."""

    errors: list[str] = []
    if schema.get("$id") != EXPECTED_SCHEMA_ID:
        errors.append("schema $id is invalid")
    if schema.get("title") != EXPECTED_SCHEMA_TITLE:
        errors.append("schema title is invalid")
    if schema.get("type") != "object":
        errors.append("schema root type must be object")
    if schema.get("additionalProperties") is not False:
        errors.append("schema root must close additional properties")
    required_fields = schema.get("required")
    properties = schema.get("properties")
    if not isinstance(required_fields, list):
        errors.append("schema required field must be a list")
    if not isinstance(properties, dict):
        errors.append("schema properties must be an object")
    if isinstance(required_fields, list) and isinstance(properties, dict):
        for field_name in (
            "report_id",
            "report_version",
            "rehearsal_scope",
            "execution_mode",
            "scenario_plan",
            "execution_results",
            "authority_boundary",
            "safety_guards",
            "receipt_refs",
            "contract_summary",
            "evidence_refs",
        ):
            if field_name not in required_fields:
                errors.append(f"schema missing required field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing property: {field_name}")
    return errors


def validate_chaos_rehearsal_execution_report_record(
    record: Any,
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one chaos rehearsal report."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("chaos rehearsal execution report must be a JSON object")
        return errors

    _validate_top_level(record, errors)
    _validate_scope(record.get("rehearsal_scope"), errors)
    _validate_execution_mode(record.get("execution_mode"), errors)
    _validate_scenario_plan(record.get("scenario_plan"), errors)
    _validate_results(record.get("execution_mode"), record.get("scenario_plan"), record.get("execution_results"), errors)
    _validate_authority_boundary(record.get("authority_boundary"), errors)
    _validate_safety_guards(record.get("safety_guards"), errors)
    _validate_receipt_refs(record.get("receipt_refs"), errors)
    _validate_contract_summary(record, errors)
    _require_subset(record, "evidence_refs", REQUIRED_ARTIFACT_REFS, errors)
    return errors


def validate_chaos_rehearsal_execution_report(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode report."""

    schema = _load_schema(schema_path)
    report = load_json_object(report_path, "ChaosRehearsalExecutionReport")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_chaos_rehearsal_execution_report_record(report, schema))
    return errors


def build_mutated_chaos_rehearsal_execution_report(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default report."""

    report = load_json_object(DEFAULT_REPORT_PATH, "ChaosRehearsalExecutionReport")
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


def workspace_display_path(path: Path) -> str:
    """Return a stable workspace-relative display path when possible."""

    resolved_path = path if path.is_absolute() else WORKSPACE_ROOT / path
    try:
        return str(resolved_path.resolve().relative_to(WORKSPACE_ROOT))
    except ValueError:
        return str(path)


def _validate_top_level(record: dict[str, Any], errors: list[str]) -> None:
    if record.get("report_version") != EXPECTED_REPORT_VERSION:
        errors.append("report_version must match chaos_rehearsal_execution_report.v1")
    for parent_name, field_name in DIGEST_REF_FIELDS:
        parent = record.get(parent_name)
        value = parent.get(field_name) if isinstance(parent, dict) else None
        _validate_digest_ref(f"{parent_name}.{field_name}", value, errors)


def _validate_scope(scope: Any, errors: list[str]) -> None:
    if not isinstance(scope, dict):
        errors.append("rehearsal_scope must be an object")
        return
    if scope.get("source_family") != "external/nested-mind-platform":
        errors.append("rehearsal_scope.source_family must be external/nested-mind-platform")
    if scope.get("borrowed_concept") != "chaos-rehearsal-dry-run":
        errors.append("rehearsal_scope.borrowed_concept must be chaos-rehearsal-dry-run")
    if scope.get("foundation_mode") is not True:
        errors.append("rehearsal_scope.foundation_mode must be true")
    if scope.get("tenant_scope") != "foundation-local-only":
        errors.append("rehearsal_scope.tenant_scope must be foundation-local-only")
    if not isinstance(scope.get("uao_ref"), str) or scope.get("uao_ref") == "":
        errors.append("rehearsal_scope.uao_ref must be non-empty")
    if scope.get("life_meaning_judgment_ref") != REQUIRED_RECEIPT_REFS["life_meaning_judgment_schema"]:
        errors.append(
            "rehearsal_scope.life_meaning_judgment_ref must be "
            f"{REQUIRED_RECEIPT_REFS['life_meaning_judgment_schema']}"
        )


def _validate_execution_mode(mode: Any, errors: list[str]) -> None:
    if not isinstance(mode, dict):
        errors.append("execution_mode must be an object")
        return
    if mode.get("mode") not in {"plan_only", "deterministic_dry_run"}:
        errors.append("execution_mode.mode must be plan_only or deterministic_dry_run")
    if mode.get("dry_run_only") is not True:
        errors.append("execution_mode.dry_run_only must be true")
    if mode.get("plan_only_allowed") is not True:
        errors.append("execution_mode.plan_only_allowed must be true")
    for field_name in (
        "production_target_allowed",
        "staging_target_allowed",
        "destructive_injection_allowed",
    ):
        if mode.get(field_name) is not False:
            errors.append(f"execution_mode.{field_name} must be false")
    runtime_target_ref = mode.get("runtime_target_ref")
    if not isinstance(runtime_target_ref, str) or not runtime_target_ref.startswith("none://"):
        errors.append("execution_mode.runtime_target_ref must use none:// dry-run target")


def _validate_scenario_plan(plan: Any, errors: list[str]) -> None:
    if not isinstance(plan, dict):
        errors.append("scenario_plan must be an object")
        return
    for field_name in (
        "scenario_refs",
        "invariant_refs",
        "injection_point_refs",
        "expected_containment_refs",
        "expected_signal_refs",
        "required_evidence_refs",
        "rollback_guard_refs",
    ):
        values = plan.get(field_name)
        if not isinstance(values, list) or not values:
            errors.append(f"scenario_plan.{field_name} must contain at least one ref")
        elif len(values) != len(set(values)):
            errors.append(f"scenario_plan.{field_name} must not contain duplicates")


def _validate_results(mode: Any, plan: Any, results: Any, errors: list[str]) -> None:
    if not isinstance(results, dict):
        errors.append("execution_results must be an object")
        return
    scenario_count = _list_len(plan.get("scenario_refs")) if isinstance(plan, dict) else None
    declared_count = results.get("scenarios_declared_count")
    executed_count = results.get("scenarios_executed_count")
    passed_count = results.get("scenarios_passed_count")
    if scenario_count is not None and declared_count != scenario_count:
        errors.append("execution_results.scenarios_declared_count must match scenario_refs count")
    if isinstance(executed_count, int) and isinstance(declared_count, int) and executed_count > declared_count:
        errors.append("execution_results.scenarios_executed_count must not exceed declared count")
    if isinstance(passed_count, int) and isinstance(executed_count, int) and passed_count > executed_count:
        errors.append("execution_results.scenarios_passed_count must not exceed executed count")
    if isinstance(mode, dict) and mode.get("mode") == "plan_only" and executed_count != 0:
        errors.append("execution_results.scenarios_executed_count must be 0 for plan_only mode")
    if results.get("unexpected_accept_count") != 0:
        errors.append("execution_results.unexpected_accept_count must be 0")
    if results.get("unexpected_reject_count") != 0:
        errors.append("execution_results.unexpected_reject_count must be 0")
    if results.get("containment_verified") is not True:
        errors.append("execution_results.containment_verified must be true")


def _validate_authority_boundary(boundary: Any, errors: list[str]) -> None:
    if not isinstance(boundary, dict):
        errors.append("authority_boundary must be an object")
        return
    for field_name in DENIED_AUTHORITY_FIELDS:
        if boundary.get(field_name) is not False:
            errors.append(f"authority_boundary.{field_name} must be false")


def _validate_safety_guards(guards: Any, errors: list[str]) -> None:
    if not isinstance(guards, dict):
        errors.append("safety_guards must be an object")
        return
    for field_name in REQUIRED_TRUE_GUARD_FIELDS:
        if guards.get(field_name) is not True:
            errors.append(f"safety_guards.{field_name} must be true")
    for field_name in REQUIRED_FALSE_GUARD_FIELDS:
        if guards.get(field_name) is not False:
            errors.append(f"safety_guards.{field_name} must be false")


def _validate_receipt_refs(refs: Any, errors: list[str]) -> None:
    if not isinstance(refs, dict):
        errors.append("receipt_refs must be an object")
        return
    for field_name, expected_ref in REQUIRED_RECEIPT_REFS.items():
        if refs.get(field_name) != expected_ref:
            errors.append(f"receipt_refs.{field_name} must be {expected_ref}")


def _validate_contract_summary(record: dict[str, Any], errors: list[str]) -> None:
    plan = record.get("scenario_plan")
    boundary = record.get("authority_boundary")
    guards = record.get("safety_guards")
    refs = record.get("receipt_refs")
    summary = record.get("contract_summary")
    if not isinstance(plan, dict) or not isinstance(boundary, dict) or not isinstance(guards, dict) or not isinstance(refs, dict) or not isinstance(summary, dict):
        errors.append("scenario_plan, authority_boundary, safety_guards, receipt_refs, and contract_summary must be typed")
        return
    if summary.get("dry_run_only") is not True:
        errors.append("contract_summary.dry_run_only must be true")
    if summary.get("runtime_disruption_denied") is not True:
        errors.append("contract_summary.runtime_disruption_denied must be true")
    expected_counts = {
        "scenario_ref_count": _list_len(plan.get("scenario_refs")),
        "invariant_ref_count": _list_len(plan.get("invariant_refs")),
        "injection_point_ref_count": _list_len(plan.get("injection_point_refs")),
        "required_evidence_ref_count": _list_len(plan.get("required_evidence_refs")),
        "rollback_guard_ref_count": _list_len(plan.get("rollback_guard_refs")),
        "authority_denial_count": len(DENIED_AUTHORITY_FIELDS),
        "safety_guard_count": len(guards),
        "receipt_ref_count": len(refs),
        "evidence_ref_count": _list_len(record.get("evidence_refs")),
    }
    for field_name, expected_count in expected_counts.items():
        if expected_count is not None and summary.get(field_name) != expected_count:
            errors.append(f"contract_summary.{field_name} must match observed count")


def _validate_digest_ref(label: str, value: Any, errors: list[str]) -> None:
    if not isinstance(value, str) or value == "":
        errors.append(f"{label} must be non-empty")
        return
    if not value.startswith("hash://sha256/"):
        errors.append(f"{label} must use hash://sha256/ digest ref")
    if "http://" in value or "https://" in value or "file://" in value:
        errors.append(f"{label} must not store raw runtime URL, file path, or body")


def _list_len(value: Any) -> int | None:
    return len(value) if isinstance(value, list) else None


def _require_subset(record: dict[str, Any], field_name: str, required_values: tuple[str, ...], errors: list[str]) -> None:
    values = record.get(field_name)
    if not isinstance(values, list):
        errors.append(f"{field_name} must be a list")
        return
    for missing_value in sorted(set(required_values) - set(values)):
        errors.append(f"{field_name} missing required ref: {missing_value}")


def main(argv: list[str] | None = None) -> int:
    """Validate ChaosRehearsalExecutionReport artifacts from the CLI."""

    parser = argparse.ArgumentParser(description="Validate ChaosRehearsalExecutionReport contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable validation receipt")
    args = parser.parse_args(argv)
    errors = validate_chaos_rehearsal_execution_report(args.schema, args.report)
    if args.json:
        print(
            json.dumps(
                {
                    "receipt_id": "chaos_rehearsal_execution_report_validation",
                    "schema_path": workspace_display_path(args.schema),
                    "report_path": workspace_display_path(args.report),
                    "status": "passed" if not errors else "failed",
                    "errors": errors,
                },
                indent=2,
                sort_keys=True,
            )
        )
    elif errors:
        for error in errors:
            print(f"[FAIL] {error}")
    else:
        print("[PASS] chaos_rehearsal_execution_report")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

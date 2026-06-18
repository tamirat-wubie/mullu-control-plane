#!/usr/bin/env python3
"""Validate the InvariantFuzzExecutionReport contract.

Purpose: verify deterministic invariant-fuzz execution evidence remains
Foundation Mode, case-bank-hash-bound, projection-leak-checked, and separated
from staging, production, canonical runtime mutation, external effects, raw
case payload retention, and terminal authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, schema validation helpers, UAO,
LifeMeaningJudgment, EffectAssurance, SimulationReceipt, WorkerFailureReceipt,
and SDLC recovery handoff schemas.
Invariants:
  - Validation is read-only and deterministic.
  - The Foundation example records only deterministic dry-run evidence.
  - Runtime execution, canonical mutation, event-chain mutation, connector
    calls, secret access, filesystem writes, rollback execution, terminal
    closure, success claims, raw case payloads, and raw secrets remain denied.
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


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "invariant_fuzz_execution_report.schema.json"
DEFAULT_REPORT_PATH = WORKSPACE_ROOT / "examples" / "invariant_fuzz_execution_report.foundation.json"

EXPECTED_SCHEMA_ID = "urn:mullusi:schema:invariant-fuzz-execution-report:1"
EXPECTED_SCHEMA_TITLE = "Invariant Fuzz Execution Report"
EXPECTED_REPORT_VERSION = "invariant_fuzz_execution_report.v1"
REQUIRED_RECEIPT_REFS = {
    "invariant_fuzz_execution_report_schema": "schemas/invariant_fuzz_execution_report.schema.json",
    "universal_action_orchestration_schema": "schemas/universal_action_orchestration.schema.json",
    "life_meaning_judgment_schema": "schemas/life_meaning_judgment.schema.json",
    "effect_assurance_schema": "schemas/effect_assurance.schema.json",
    "simulation_receipt_schema": "schemas/simulation_receipt.schema.json",
    "worker_failure_receipt_schema": "schemas/worker_failure_receipt.schema.json",
    "sdlc_recovery_handoff_receipt_schema": "schemas/sdlc_recovery_handoff_receipt.schema.json",
}
REQUIRED_ARTIFACT_REFS = (
    "schemas/invariant_fuzz_execution_report.schema.json",
    "examples/invariant_fuzz_execution_report.foundation.json",
    "scripts/validate_invariant_fuzz_execution_report.py",
    "tests/test_validate_invariant_fuzz_execution_report.py",
    "docs/92_invariant_fuzz_execution_report_contract.md",
    "docs/82_cross_repo_opportunity_map.md",
    "schemas/universal_action_orchestration.schema.json",
    "schemas/life_meaning_judgment.schema.json",
    "schemas/effect_assurance.schema.json",
    "schemas/simulation_receipt.schema.json",
    "schemas/sdlc_recovery_handoff_receipt.schema.json",
)
REQUIRED_MUTATION_CLASS_REFS = {
    "mutation://empty_patch",
    "mutation://immutable_identity_change",
    "mutation://required_key_removal",
    "mutation://forbidden_key_insertion",
    "mutation://wrong_target",
    "mutation://valid_state_expansion",
    "mutation://projection_secret_leak_probe",
}
DENIED_AUTHORITY_FIELDS = (
    "live_runtime_execution_performed",
    "production_target_touched",
    "staging_cluster_touched",
    "canonical_state_mutation_performed",
    "event_chain_mutation_performed",
    "lawbook_runtime_migration_performed",
    "external_connector_called",
    "secret_access_performed",
    "filesystem_write_performed",
    "rollback_executed",
    "terminal_closure_allowed",
    "success_claim_allowed",
)
REQUIRED_TRUE_GUARD_FIELDS = (
    "case_bank_hash_required",
    "deterministic_seed_required",
    "oracle_refs_required",
    "projection_leak_check_required",
    "expected_accept_reject_declared",
    "operator_review_required",
    "incident_handoff_required_if_live",
)
REQUIRED_FALSE_GUARD_FIELDS = (
    "raw_case_payload_retained",
    "raw_secret_material_retained",
)
DIGEST_REF_FIELDS = (
    ("case_bank", "case_bank_hash_ref"),
    ("execution_results", "result_bank_hash_ref"),
)


class InvariantFuzzExecutionReportError(ValueError):
    """Raised when an InvariantFuzzExecutionReport artifact cannot load."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    path = json_path if json_path.is_absolute() else WORKSPACE_ROOT / json_path
    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise InvariantFuzzExecutionReportError(f"{label} must be a JSON object")
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
            "fuzz_scope",
            "harness_mode",
            "case_bank",
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


def validate_invariant_fuzz_execution_report_record(
    record: Any,
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one invariant fuzz report."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("invariant fuzz execution report must be a JSON object")
        return errors

    _validate_top_level(record, errors)
    _validate_scope(record.get("fuzz_scope"), errors)
    _validate_harness_mode(record.get("harness_mode"), errors)
    _validate_case_bank(record.get("case_bank"), errors)
    _validate_results(record.get("harness_mode"), record.get("case_bank"), record.get("execution_results"), errors)
    _validate_authority_boundary(record.get("authority_boundary"), errors)
    _validate_safety_guards(record.get("safety_guards"), errors)
    _validate_receipt_refs(record.get("receipt_refs"), errors)
    _validate_contract_summary(record, errors)
    _require_subset(record, "evidence_refs", REQUIRED_ARTIFACT_REFS, errors)
    return errors


def validate_invariant_fuzz_execution_report(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode report."""

    schema = _load_schema(schema_path)
    report = load_json_object(report_path, "InvariantFuzzExecutionReport")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_invariant_fuzz_execution_report_record(report, schema))
    return errors


def build_mutated_invariant_fuzz_execution_report(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default report."""

    report = load_json_object(DEFAULT_REPORT_PATH, "InvariantFuzzExecutionReport")
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
        errors.append("report_version must match invariant_fuzz_execution_report.v1")
    for parent_name, field_name in DIGEST_REF_FIELDS:
        parent = record.get(parent_name)
        value = parent.get(field_name) if isinstance(parent, dict) else None
        _validate_digest_ref(f"{parent_name}.{field_name}", value, errors)


def _validate_scope(scope: Any, errors: list[str]) -> None:
    if not isinstance(scope, dict):
        errors.append("fuzz_scope must be an object")
        return
    if scope.get("source_family") != "external/nested-mind-platform":
        errors.append("fuzz_scope.source_family must be external/nested-mind-platform")
    if scope.get("borrowed_concept") != "invariant-fuzz-execution":
        errors.append("fuzz_scope.borrowed_concept must be invariant-fuzz-execution")
    if scope.get("foundation_mode") is not True:
        errors.append("fuzz_scope.foundation_mode must be true")
    if scope.get("tenant_scope") != "foundation-local-only":
        errors.append("fuzz_scope.tenant_scope must be foundation-local-only")
    if not isinstance(scope.get("uao_ref"), str) or scope.get("uao_ref") == "":
        errors.append("fuzz_scope.uao_ref must be non-empty")
    if scope.get("life_meaning_judgment_ref") != REQUIRED_RECEIPT_REFS["life_meaning_judgment_schema"]:
        errors.append(
            "fuzz_scope.life_meaning_judgment_ref must be "
            f"{REQUIRED_RECEIPT_REFS['life_meaning_judgment_schema']}"
        )


def _validate_harness_mode(mode: Any, errors: list[str]) -> None:
    if not isinstance(mode, dict):
        errors.append("harness_mode must be an object")
        return
    if mode.get("mode") not in {"plan_only", "deterministic_dry_run"}:
        errors.append("harness_mode.mode must be plan_only or deterministic_dry_run")
    for field_name in (
        "dry_run_only",
        "strict_baseline_required",
        "projection_redaction_required",
    ):
        if mode.get(field_name) is not True:
            errors.append(f"harness_mode.{field_name} must be true")
    if mode.get("apply_successful_cases") is not True:
        errors.append("harness_mode.apply_successful_cases must be true for result-bank accounting")
    for field_name in ("production_target_allowed", "staging_target_allowed"):
        if mode.get(field_name) is not False:
            errors.append(f"harness_mode.{field_name} must be false")
    runtime_target_ref = mode.get("runtime_target_ref")
    if not isinstance(runtime_target_ref, str) or not runtime_target_ref.startswith("none://"):
        errors.append("harness_mode.runtime_target_ref must use none:// dry-run target")


def _validate_case_bank(case_bank: Any, errors: list[str]) -> None:
    if not isinstance(case_bank, dict):
        errors.append("case_bank must be an object")
        return
    mutation_class_refs = case_bank.get("mutation_class_refs")
    oracle_refs = case_bank.get("oracle_refs")
    if not isinstance(mutation_class_refs, list) or not mutation_class_refs:
        errors.append("case_bank.mutation_class_refs must contain at least one ref")
    elif len(mutation_class_refs) != len(set(mutation_class_refs)):
        errors.append("case_bank.mutation_class_refs must not contain duplicates")
    elif set(mutation_class_refs) != REQUIRED_MUTATION_CLASS_REFS:
        errors.append("case_bank.mutation_class_refs must match required mutation classes")
    if not isinstance(oracle_refs, list) or not oracle_refs:
        errors.append("case_bank.oracle_refs must contain at least one ref")
    elif len(oracle_refs) != len(set(oracle_refs)):
        errors.append("case_bank.oracle_refs must not contain duplicates")
    declared_count = case_bank.get("declared_case_count")
    expected_accept_count = case_bank.get("expected_accept_count")
    expected_reject_count = case_bank.get("expected_reject_count")
    projection_probe_count = case_bank.get("projection_probe_count")
    if isinstance(mutation_class_refs, list) and declared_count != len(mutation_class_refs):
        errors.append("case_bank.declared_case_count must match mutation_class_refs count")
    if isinstance(oracle_refs, list) and declared_count != len(oracle_refs):
        errors.append("case_bank.declared_case_count must match oracle_refs count")
    if isinstance(expected_accept_count, int) and isinstance(expected_reject_count, int) and isinstance(declared_count, int):
        if expected_accept_count + expected_reject_count != declared_count:
            errors.append("case_bank expected accept and reject counts must sum to declared count")
    if projection_probe_count != 1:
        errors.append("case_bank.projection_probe_count must be 1")


def _validate_results(mode: Any, case_bank: Any, results: Any, errors: list[str]) -> None:
    if not isinstance(results, dict):
        errors.append("execution_results must be an object")
        return
    declared_count = case_bank.get("declared_case_count") if isinstance(case_bank, dict) else None
    executed_count = results.get("cases_executed_count")
    passed_count = results.get("cases_passed_count")
    failed_count = results.get("cases_failed_count")
    if isinstance(mode, dict) and mode.get("mode") == "plan_only" and executed_count != 0:
        errors.append("execution_results.cases_executed_count must be 0 for plan_only mode")
    if isinstance(executed_count, int) and isinstance(declared_count, int) and executed_count > declared_count:
        errors.append("execution_results.cases_executed_count must not exceed declared count")
    if isinstance(passed_count, int) and isinstance(executed_count, int) and passed_count > executed_count:
        errors.append("execution_results.cases_passed_count must not exceed executed count")
    if isinstance(failed_count, int) and isinstance(passed_count, int) and isinstance(executed_count, int):
        if passed_count + failed_count != executed_count:
            errors.append("execution_results passed and failed counts must sum to executed count")
    if results.get("unexpected_accept_count") != 0:
        errors.append("execution_results.unexpected_accept_count must be 0")
    if results.get("unexpected_reject_count") != 0:
        errors.append("execution_results.unexpected_reject_count must be 0")
    if results.get("projection_leak_detected") is not False:
        errors.append("execution_results.projection_leak_detected must be false")
    if results.get("public_projection_checked") is not True:
        errors.append("execution_results.public_projection_checked must be true")


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
    case_bank = record.get("case_bank")
    boundary = record.get("authority_boundary")
    guards = record.get("safety_guards")
    refs = record.get("receipt_refs")
    summary = record.get("contract_summary")
    if not isinstance(case_bank, dict) or not isinstance(boundary, dict) or not isinstance(guards, dict) or not isinstance(refs, dict) or not isinstance(summary, dict):
        errors.append("case_bank, authority_boundary, safety_guards, receipt_refs, and contract_summary must be typed")
        return
    if summary.get("dry_run_only") is not True:
        errors.append("contract_summary.dry_run_only must be true")
    if summary.get("canonical_mutation_denied") is not True:
        errors.append("contract_summary.canonical_mutation_denied must be true")
    expected_counts = {
        "mutation_class_count": _list_len(case_bank.get("mutation_class_refs")),
        "oracle_ref_count": _list_len(case_bank.get("oracle_refs")),
        "declared_case_count": case_bank.get("declared_case_count"),
        "expected_accept_count": case_bank.get("expected_accept_count"),
        "expected_reject_count": case_bank.get("expected_reject_count"),
        "projection_probe_count": case_bank.get("projection_probe_count"),
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
    """Validate InvariantFuzzExecutionReport artifacts from the CLI."""

    parser = argparse.ArgumentParser(description="Validate InvariantFuzzExecutionReport contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable validation receipt")
    args = parser.parse_args(argv)
    errors = validate_invariant_fuzz_execution_report(args.schema, args.report)
    if args.json:
        print(
            json.dumps(
                {
                    "receipt_id": "invariant_fuzz_execution_report_validation",
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
        print("[PASS] invariant_fuzz_execution_report")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

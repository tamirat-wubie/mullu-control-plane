#!/usr/bin/env python3
"""Validate the SchedulerWorkerRuntimeReceiptHandoff contract.

Purpose: verify the Foundation Mode handoff from temporal scheduler and
distributed lease execution receipts toward future worker runtime receipt
emission without granting scheduler dispatch, runtime dispatch, worker
invocation, backend calls, filesystem writes, connector authority, or terminal
closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library and schema validation helpers.
Invariants:
  - Validation is read-only and deterministic.
  - The handoff binds scheduler and distributed lease execution receipt refs.
  - Runtime dispatch, worker invocation, backend calls, and terminal closure
    remain denied until named evidence exists.
  - Mfidel atomicity remains preserved.
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


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "scheduler_worker_runtime_receipt_handoff.schema.json"
DEFAULT_HANDOFF_PATH = WORKSPACE_ROOT / "examples" / "scheduler_worker_runtime_receipt_handoff.foundation.json"
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:scheduler-worker-runtime-receipt-handoff:1"
EXPECTED_SCHEMA_TITLE = "Scheduler Worker Runtime Receipt Handoff"
EXPECTED_HANDOFF_VERSION = "scheduler_worker_runtime_receipt_handoff.v1"
EXPECTED_SCHEDULER_REF = "receipt://temporal-scheduler/foundation-leased-command"
EXPECTED_DISTRIBUTED_LEASE_EXECUTION_REF = "receipt://distributed-lease-execution/foundation-scheduler-worker"
EXPECTED_WORKER_MESH_REF = "schemas/worker_mesh.schema.json"
EXPECTED_WORKER_FAILURE_REF = "schemas/worker_failure_receipt.schema.json"
EXPECTED_OPERATION_FAMILY = "scheduler_worker_runtime_receipt_handoff"
EXPECTED_HANDOFF_STATE = "FOUNDATION_HANDOFF_RECORDED"
EXPECTED_RESULT_STATE = "HANDOFF_RECORDED"
REQUIRED_SOURCE_RECEIPT_REFS = (
    "schemas/temporal_scheduler_receipt.schema.json",
    "schemas/distributed_lease_execution_receipt.schema.json",
    "schemas/worker_mesh.schema.json",
    "schemas/worker_failure_receipt.schema.json",
    "schemas/universal_action_orchestration.schema.json",
)
REQUIRED_ADMISSION_GATE_REFS = (
    "gate://temporal-scheduler-leased",
    "gate://distributed-lease-execution-receipt-ready",
    "gate://uao-effect-admission",
    "gate://phi-gov-dispatch-authorization",
    "gate://worker-runtime-receipt-emitter",
    "gate://worker-failure-receipt-on-error",
    "gate://effect-reconciliation-before-terminal-closure",
)
REQUIRED_RUNTIME_WITNESS_REFS = (
    "witness://scheduler-dispatch/not-registered",
    "witness://runtime-dispatch/not-registered",
    "witness://worker-invocation/not-registered",
    "witness://runtime-receipt-emitter/not-registered",
    "witness://runtime-receipt-schema/not-bound",
)
REQUIRED_RECEIPT_SCHEMA_REFS = (
    "schemas/scheduler_worker_runtime_receipt_handoff.schema.json",
    "schemas/temporal_scheduler_receipt.schema.json",
    "schemas/distributed_lease_execution_receipt.schema.json",
    "schemas/distributed_lease_adapter_registry_receipt.schema.json",
    "schemas/distributed_lease_claim_receipt.schema.json",
    "schemas/worker_mesh.schema.json",
    "schemas/worker_failure_receipt.schema.json",
    "schemas/universal_action_orchestration.schema.json",
)
REQUIRED_VALIDATION_REFS = (
    "scripts/validate_scheduler_worker_runtime_receipt_handoff.py",
    "scripts/validate_schemas.py",
    "scripts/validate_protocol_manifest.py",
    "scripts/proof_coverage_matrix.py",
)
REQUIRED_DENIED_UNTIL_REFS = (
    "evidence://temporal-scheduler-runtime-receipt",
    "evidence://distributed-lease-execution-runtime-receipt",
    "evidence://worker-runtime-receipt-emitter-dry-run",
    "evidence://uao-effect-admission",
    "evidence://phi-gov-dispatch-authorization",
    "evidence://effect-reconciliation-receipt",
)
REQUIRED_RECEIPT_REFS = {
    "scheduler_worker_runtime_receipt_handoff_schema": "schemas/scheduler_worker_runtime_receipt_handoff.schema.json",
    "temporal_scheduler_receipt_schema": "schemas/temporal_scheduler_receipt.schema.json",
    "distributed_lease_execution_receipt_schema": "schemas/distributed_lease_execution_receipt.schema.json",
    "distributed_lease_adapter_registry_receipt_schema": "schemas/distributed_lease_adapter_registry_receipt.schema.json",
    "distributed_lease_claim_receipt_schema": "schemas/distributed_lease_claim_receipt.schema.json",
    "worker_mesh_schema": "schemas/worker_mesh.schema.json",
    "worker_failure_receipt_schema": "schemas/worker_failure_receipt.schema.json",
    "universal_action_orchestration_schema": "schemas/universal_action_orchestration.schema.json",
}
REQUIRED_EVIDENCE_REFS = (
    "schemas/scheduler_worker_runtime_receipt_handoff.schema.json",
    "examples/scheduler_worker_runtime_receipt_handoff.foundation.json",
    "scripts/validate_scheduler_worker_runtime_receipt_handoff.py",
    "tests/test_validate_scheduler_worker_runtime_receipt_handoff.py",
    "schemas/temporal_scheduler_receipt.schema.json",
    "schemas/distributed_lease_execution_receipt.schema.json",
    "schemas/distributed_lease_adapter_registry_receipt.schema.json",
    "schemas/distributed_lease_claim_receipt.schema.json",
    "schemas/worker_mesh.schema.json",
    "schemas/worker_failure_receipt.schema.json",
    "schemas/universal_action_orchestration.schema.json",
    "scripts/proof_coverage_matrix.py",
)
DENIED_AUTHORITY_FIELDS = (
    "scheduler_dispatch_allowed",
    "runtime_dispatch_allowed",
    "worker_invocation_allowed",
    "scheduler_mutation_allowed",
    "lease_backend_call_allowed",
    "adapter_backend_call_allowed",
    "external_network_allowed",
    "secret_access_allowed",
    "filesystem_write_allowed",
    "connector_authority_allowed",
    "terminal_closure_allowed",
    "success_claim_allowed",
)
REQUIRED_TRUE_ADMISSION_GUARDS = (
    "temporal_scheduler_receipt_required",
    "distributed_lease_execution_receipt_required",
    "worker_mesh_receipt_required",
    "worker_failure_receipt_required_on_error",
    "uao_effect_admission_required",
    "phi_gov_dispatch_authorization_required",
    "effect_reconciliation_required",
    "terminal_closure_blocked_until_runtime_receipt",
)
DENIED_ADMISSION_GUARDS = (
    "scheduler_dispatch_registered",
    "runtime_dispatch_registered",
    "worker_invocation_registered",
    "runtime_receipt_emitter_registered",
    "runtime_receipt_schema_bound",
)
DENIED_RESULT_FIELDS = (
    "scheduler_dispatch_performed",
    "runtime_dispatch_performed",
    "worker_invocation_performed",
    "lease_backend_call_performed",
    "adapter_backend_call_performed",
    "scheduler_mutation_performed",
    "external_effects_observed",
    "filesystem_writes_observed",
    "connector_calls_observed",
    "terminal_closure",
    "success_claim_allowed",
)


class SchedulerWorkerRuntimeReceiptHandoffError(ValueError):
    """Raised when a SchedulerWorkerRuntimeReceiptHandoff artifact cannot load."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    resolved_path = json_path if json_path.is_absolute() else WORKSPACE_ROOT / json_path
    if not resolved_path.exists():
        raise FileNotFoundError(f"missing {label}: {resolved_path}")
    if not resolved_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {resolved_path}")
    payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SchedulerWorkerRuntimeReceiptHandoffError(f"{label} must be a JSON object")
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
            "handoff_id",
            "handoff_version",
            "scheduler_receipt_ref",
            "distributed_lease_execution_receipt_ref",
            "worker_mesh_ref",
            "worker_failure_receipt_ref",
            "authority_scope",
            "scheduler_worker_contract",
            "admission_guards",
            "handoff_result",
            "receipt_refs",
            "contract_summary",
            "evidence_refs",
        ):
            if field_name not in required_fields:
                errors.append(f"schema missing required field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing property: {field_name}")
    return errors


def validate_handoff_record(record: Any, schema: dict[str, Any] | None = None) -> list[str]:
    """Return deterministic validation errors for one handoff record."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("scheduler worker runtime receipt handoff must be a JSON object")
        return errors

    _validate_top_level_refs(record, errors)
    _validate_authority_scope(record.get("authority_scope"), errors)
    _validate_scheduler_worker_contract(record.get("scheduler_worker_contract"), errors)
    _validate_admission_guards(record.get("admission_guards"), errors)
    _validate_handoff_result(record.get("handoff_result"), errors)
    _validate_receipt_refs(record.get("receipt_refs"), errors)
    _validate_contract_summary(record, errors)
    _require_subset(record, "evidence_refs", REQUIRED_EVIDENCE_REFS, errors)
    return errors


def validate_scheduler_worker_runtime_receipt_handoff(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    handoff_path: Path = DEFAULT_HANDOFF_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode handoff."""

    schema = _load_schema(schema_path)
    handoff = load_json_object(handoff_path, "SchedulerWorkerRuntimeReceiptHandoff")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_handoff_record(handoff, schema))
    return errors


def build_mutated_handoff(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default handoff for tests."""

    handoff = load_json_object(DEFAULT_HANDOFF_PATH, "SchedulerWorkerRuntimeReceiptHandoff")
    mutated = deepcopy(handoff)
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


def _validate_top_level_refs(record: dict[str, Any], errors: list[str]) -> None:
    if record.get("handoff_version") != EXPECTED_HANDOFF_VERSION:
        errors.append("handoff_version must match scheduler_worker_runtime_receipt_handoff.v1")
    if record.get("scheduler_receipt_ref") != EXPECTED_SCHEDULER_REF:
        errors.append("scheduler_receipt_ref must point to the Foundation scheduler receipt ref")
    if record.get("distributed_lease_execution_receipt_ref") != EXPECTED_DISTRIBUTED_LEASE_EXECUTION_REF:
        errors.append("distributed_lease_execution_receipt_ref must point to the Foundation distributed lease execution ref")
    if record.get("worker_mesh_ref") != EXPECTED_WORKER_MESH_REF:
        errors.append("worker_mesh_ref must point to the WorkerMesh schema")
    if record.get("worker_failure_receipt_ref") != EXPECTED_WORKER_FAILURE_REF:
        errors.append("worker_failure_receipt_ref must point to the WorkerFailureReceipt schema")


def _validate_authority_scope(scope: Any, errors: list[str]) -> None:
    if not isinstance(scope, dict):
        errors.append("authority_scope must be an object")
        return
    if scope.get("foundation_handoff_only") is not True:
        errors.append("authority_scope.foundation_handoff_only must be true")
    for field_name in DENIED_AUTHORITY_FIELDS:
        if scope.get(field_name) is not False:
            errors.append(f"authority_scope.{field_name} must be false")
    if scope.get("mfidel_atomicity_preserved") is not True:
        errors.append("authority_scope.mfidel_atomicity_preserved must be true")


def _validate_scheduler_worker_contract(contract: Any, errors: list[str]) -> None:
    if not isinstance(contract, dict):
        errors.append("scheduler_worker_contract must be an object")
        return
    if contract.get("operation_family") != EXPECTED_OPERATION_FAMILY:
        errors.append("scheduler_worker_contract.operation_family must be scheduler_worker_runtime_receipt_handoff")
    if contract.get("handoff_state") != EXPECTED_HANDOFF_STATE:
        errors.append("scheduler_worker_contract.handoff_state must be FOUNDATION_HANDOFF_RECORDED")
    _require_subset(contract, "required_source_receipt_refs", REQUIRED_SOURCE_RECEIPT_REFS, errors)
    _require_subset(contract, "required_admission_gate_refs", REQUIRED_ADMISSION_GATE_REFS, errors)
    _require_subset(contract, "required_runtime_witness_refs", REQUIRED_RUNTIME_WITNESS_REFS, errors)
    _require_subset(contract, "receipt_schema_refs", REQUIRED_RECEIPT_SCHEMA_REFS, errors)
    _require_subset(contract, "validation_refs", REQUIRED_VALIDATION_REFS, errors)
    _require_subset(contract, "denied_until_refs", REQUIRED_DENIED_UNTIL_REFS, errors)
    obligations = contract.get("future_worker_receipt_obligations")
    if not isinstance(obligations, list) or len(obligations) < 7:
        errors.append("future_worker_receipt_obligations must list scheduler-to-worker runtime receipt obligations")
    elif not any(isinstance(item, str) and "WorkerFailureReceipt" in item for item in obligations):
        errors.append("future_worker_receipt_obligations must require WorkerFailureReceipt on failure")


def _validate_admission_guards(guards: Any, errors: list[str]) -> None:
    if not isinstance(guards, dict):
        errors.append("admission_guards must be an object")
        return
    for field_name in REQUIRED_TRUE_ADMISSION_GUARDS:
        if guards.get(field_name) is not True:
            errors.append(f"admission_guards.{field_name} must be true")
    for field_name in DENIED_ADMISSION_GUARDS:
        if guards.get(field_name) is not False:
            errors.append(f"admission_guards.{field_name} must be false")


def _validate_handoff_result(result: Any, errors: list[str]) -> None:
    if not isinstance(result, dict):
        errors.append("handoff_result must be an object")
        return
    if result.get("result_state") != EXPECTED_RESULT_STATE:
        errors.append("handoff_result.result_state must be HANDOFF_RECORDED for the default handoff")
    next_evidence = result.get("next_required_evidence")
    if not isinstance(next_evidence, list) or len(next_evidence) < 5:
        errors.append("handoff_result.next_required_evidence must list future runtime evidence")
    for field_name in DENIED_RESULT_FIELDS:
        if result.get(field_name) is not False:
            errors.append(f"handoff_result.{field_name} must be false")


def _validate_receipt_refs(refs: Any, errors: list[str]) -> None:
    if not isinstance(refs, dict):
        errors.append("receipt_refs must be an object")
        return
    for field_name, expected_ref in REQUIRED_RECEIPT_REFS.items():
        if refs.get(field_name) != expected_ref:
            errors.append(f"receipt_refs.{field_name} must be {expected_ref}")


def _validate_contract_summary(record: dict[str, Any], errors: list[str]) -> None:
    contract = record.get("scheduler_worker_contract")
    result = record.get("handoff_result")
    refs = record.get("receipt_refs")
    summary = record.get("contract_summary")
    if not isinstance(contract, dict) or not isinstance(result, dict) or not isinstance(refs, dict) or not isinstance(summary, dict):
        errors.append("scheduler_worker_contract, handoff_result, receipt_refs, and contract_summary must be objects")
        return
    expected_counts = {
        "source_receipt_ref_count": _list_len(contract.get("required_source_receipt_refs")),
        "admission_gate_ref_count": _list_len(contract.get("required_admission_gate_refs")),
        "runtime_witness_ref_count": _list_len(contract.get("required_runtime_witness_refs")),
        "receipt_schema_ref_count": _list_len(contract.get("receipt_schema_refs")),
        "validation_ref_count": _list_len(contract.get("validation_refs")),
        "denied_until_ref_count": _list_len(contract.get("denied_until_refs")),
        "future_worker_obligation_count": _list_len(contract.get("future_worker_receipt_obligations")),
        "next_required_evidence_count": _list_len(result.get("next_required_evidence")),
        "receipt_ref_count": len(refs),
        "evidence_ref_count": _list_len(record.get("evidence_refs")),
    }
    for field_name, expected_count in expected_counts.items():
        if expected_count is not None and summary.get(field_name) != expected_count:
            errors.append(f"contract_summary.{field_name} must match observed count")


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
    """Validate SchedulerWorkerRuntimeReceiptHandoff artifacts from the CLI."""

    parser = argparse.ArgumentParser(description="Validate SchedulerWorkerRuntimeReceiptHandoff contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--handoff", type=Path, default=DEFAULT_HANDOFF_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable receipt")
    args = parser.parse_args(argv)
    errors = validate_scheduler_worker_runtime_receipt_handoff(args.schema, args.handoff)
    if args.json:
        print(
            json.dumps(
                {
                    "receipt_id": "scheduler_worker_runtime_receipt_handoff_validation",
                    "schema_path": workspace_display_path(args.schema),
                    "handoff_path": workspace_display_path(args.handoff),
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
        print("[PASS] scheduler_worker_runtime_receipt_handoff")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

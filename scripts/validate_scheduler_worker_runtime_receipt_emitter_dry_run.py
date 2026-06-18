#!/usr/bin/env python3
"""Validate the SchedulerWorkerRuntimeReceiptEmitterDryRun contract.

Purpose: verify Foundation Mode dry-run evidence for a future scheduler-worker
runtime receipt emitter without registering runners or emitters, dispatching a
scheduler command, invoking a worker, calling backends, writing files, calling
connectors, or claiming terminal closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, schema validation helpers, and
SchedulerWorkerRuntimeReceiptHandoff validation.
Invariants:
  - Validation is read-only and deterministic.
  - The dry-run binds SchedulerWorkerRuntimeReceiptHandoff source refs.
  - Runtime receipt emission, worker mesh dispatch, worker invocation, backend
    calls, and terminal closure remain denied.
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

from scripts.validate_scheduler_worker_runtime_receipt_handoff import (  # noqa: E402
    DEFAULT_HANDOFF_PATH,
    EXPECTED_DISTRIBUTED_LEASE_EXECUTION_REF,
    EXPECTED_SCHEDULER_REF,
    EXPECTED_WORKER_FAILURE_REF,
    EXPECTED_WORKER_MESH_REF,
    load_json_object as load_handoff_json_object,
    validate_handoff_record,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "scheduler_worker_runtime_receipt_emitter_dry_run.schema.json"
DEFAULT_RECEIPT_PATH = WORKSPACE_ROOT / "examples" / "scheduler_worker_runtime_receipt_emitter_dry_run.foundation.json"
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:scheduler-worker-runtime-receipt-emitter-dry-run:1"
EXPECTED_SCHEMA_TITLE = "Scheduler Worker Runtime Receipt Emitter Dry Run"
EXPECTED_RECEIPT_VERSION = "scheduler_worker_runtime_receipt_emitter_dry_run.v1"
EXPECTED_HANDOFF_REF = "examples/scheduler_worker_runtime_receipt_handoff.foundation.json"
EXPECTED_OPERATION_FAMILY = "scheduler_worker_runtime_receipt_emitter_dry_run"
EXPECTED_DRY_RUN_MODE = "EMITTER_DRY_RUN_ONLY"
EXPECTED_RESULT_STATE = "DRY_RUN_RECORDED"
EXPECTED_ADMISSION_DECISION = "DISPATCH_BLOCKED_AWAITING_RUNTIME_EVIDENCE"
REQUIRED_SOURCE_RECEIPT_REFS = (
    EXPECTED_HANDOFF_REF,
    "schemas/temporal_scheduler_receipt.schema.json",
    "schemas/distributed_lease_execution_receipt.schema.json",
    "schemas/worker_mesh.schema.json",
    "schemas/worker_failure_receipt.schema.json",
    "schemas/universal_action_orchestration.schema.json",
)
REQUIRED_RUNTIME_GATE_REFS = (
    "gate://temporal-scheduler-leased",
    "gate://distributed-lease-execution-receipt-ready",
    "gate://uao-effect-admission",
    "gate://phi-gov-dispatch-authorization",
    "gate://runtime-receipt-emitter-registration",
    "gate://runtime-receipt-schema-binding",
    "gate://worker-mesh-dispatch-receipt",
    "gate://worker-failure-receipt-on-error",
    "gate://effect-reconciliation-before-terminal-closure",
)
REQUIRED_RUNTIME_WITNESS_REFS = (
    "witness://scheduler-dispatch/not-registered",
    "witness://runtime-runner/not-registered",
    "witness://dispatch-endpoint/not-registered",
    "witness://worker-invocation/not-registered",
    "witness://runtime-receipt-emitter/not-registered",
    "witness://runtime-receipt-schema/not-bound",
)
REQUIRED_VALIDATION_REFS = (
    "scripts/validate_scheduler_worker_runtime_receipt_emitter_dry_run.py",
    "scripts/validate_scheduler_worker_runtime_receipt_handoff.py",
    "scripts/validate_schemas.py",
    "scripts/validate_protocol_manifest.py",
    "scripts/proof_coverage_matrix.py",
)
REQUIRED_REMAINING_DENIED_UNTIL_REFS = (
    "evidence://runtime-runner-registration",
    "evidence://runtime-receipt-emitter-registration",
    "evidence://runtime-receipt-schema-binding",
    "evidence://worker-mesh-dispatch-receipt",
    "evidence://worker-runtime-receipt",
    "evidence://uao-effect-admission",
    "evidence://phi-gov-dispatch-authorization",
    "evidence://effect-reconciliation-receipt",
)
REQUIRED_BLOCKED_REASON_REFS = (
    "blocked://scheduler-dispatch/not-registered",
    "blocked://runtime-runner/not-registered",
    "blocked://dispatch-endpoint/not-registered",
    "blocked://worker-invocation/not-registered",
    "blocked://runtime-receipt-emitter/not-registered",
    "blocked://runtime-receipt-schema/not-bound",
    "blocked://phi-gov/dispatch-not-authorized",
)
REQUIRED_RECEIPT_REFS = {
    "scheduler_worker_runtime_receipt_emitter_dry_run_schema": (
        "schemas/scheduler_worker_runtime_receipt_emitter_dry_run.schema.json"
    ),
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
    "schemas/scheduler_worker_runtime_receipt_emitter_dry_run.schema.json",
    "examples/scheduler_worker_runtime_receipt_emitter_dry_run.foundation.json",
    "scripts/validate_scheduler_worker_runtime_receipt_emitter_dry_run.py",
    "tests/test_validate_scheduler_worker_runtime_receipt_emitter_dry_run.py",
    "schemas/scheduler_worker_runtime_receipt_handoff.schema.json",
    EXPECTED_HANDOFF_REF,
    "scripts/validate_scheduler_worker_runtime_receipt_handoff.py",
    "tests/test_validate_scheduler_worker_runtime_receipt_handoff.py",
    "schemas/temporal_scheduler_receipt.schema.json",
    "schemas/distributed_lease_execution_receipt.schema.json",
    "schemas/worker_mesh.schema.json",
    "schemas/worker_failure_receipt.schema.json",
    "schemas/universal_action_orchestration.schema.json",
    "scripts/proof_coverage_matrix.py",
)
DENIED_AUTHORITY_FIELDS = (
    "scheduler_dispatch_allowed",
    "runtime_runner_registration_allowed",
    "dispatch_endpoint_registration_allowed",
    "runtime_receipt_emitter_registration_allowed",
    "runtime_receipt_schema_binding_allowed",
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
DENIED_RESULT_FIELDS = (
    "scheduler_dispatch_performed",
    "runtime_receipt_emitted",
    "worker_mesh_dispatch_receipt_emitted",
    "worker_invocation_performed",
    "raw_output_included",
    "raw_secret_material_included",
    "external_effects_observed",
    "filesystem_writes_observed",
    "connector_calls_observed",
    "terminal_closure",
    "success_claim_allowed",
)


class SchedulerWorkerRuntimeReceiptEmitterDryRunError(ValueError):
    """Raised when a SchedulerWorkerRuntimeReceiptEmitterDryRun artifact cannot load."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    resolved_path = json_path if json_path.is_absolute() else WORKSPACE_ROOT / json_path
    if not resolved_path.exists():
        raise FileNotFoundError(f"missing {label}: {resolved_path}")
    if not resolved_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {resolved_path}")
    payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SchedulerWorkerRuntimeReceiptEmitterDryRunError(f"{label} must be a JSON object")
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
            "receipt_id",
            "receipt_version",
            "handoff_ref",
            "authority_scope",
            "dry_run_contract",
            "simulated_emission_result",
            "admission_decision",
            "receipt_refs",
            "contract_summary",
            "evidence_refs",
        ):
            if field_name not in required_fields:
                errors.append(f"schema missing required field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing property: {field_name}")
    return errors


def validate_emitter_dry_run_record(
    record: Any,
    schema: dict[str, Any] | None = None,
    handoff: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one emitter dry-run receipt."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("scheduler worker runtime receipt emitter dry-run must be a JSON object")
        return errors

    handoff_payload = handoff or load_handoff_json_object(DEFAULT_HANDOFF_PATH, "SchedulerWorkerRuntimeReceiptHandoff")
    errors.extend(f"handoff: {error}" for error in validate_handoff_record(handoff_payload))
    _validate_top_level_refs(record, handoff_payload, errors)
    _validate_authority_scope(record.get("authority_scope"), errors)
    _validate_dry_run_contract(record.get("dry_run_contract"), handoff_payload, errors)
    _validate_simulated_emission_result(record.get("simulated_emission_result"), errors)
    _validate_admission_decision(record.get("admission_decision"), errors)
    _validate_receipt_refs(record.get("receipt_refs"), errors)
    _validate_contract_summary(record, errors)
    _require_subset(record, "evidence_refs", REQUIRED_EVIDENCE_REFS, errors)
    return errors


def validate_emitter_dry_run(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
    handoff_path: Path = DEFAULT_HANDOFF_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode dry-run receipt."""

    schema = _load_schema(schema_path)
    receipt = load_json_object(receipt_path, "SchedulerWorkerRuntimeReceiptEmitterDryRun")
    handoff = load_handoff_json_object(handoff_path, "SchedulerWorkerRuntimeReceiptHandoff")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_emitter_dry_run_record(receipt, schema, handoff))
    return errors


def build_mutated_emitter_dry_run(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default dry-run receipt."""

    receipt = load_json_object(DEFAULT_RECEIPT_PATH, "SchedulerWorkerRuntimeReceiptEmitterDryRun")
    mutated = deepcopy(receipt)
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


def _validate_top_level_refs(record: dict[str, Any], handoff: dict[str, Any], errors: list[str]) -> None:
    if record.get("receipt_version") != EXPECTED_RECEIPT_VERSION:
        errors.append("receipt_version must match scheduler_worker_runtime_receipt_emitter_dry_run.v1")
    if record.get("handoff_ref") != EXPECTED_HANDOFF_REF:
        errors.append("handoff_ref must point to the SchedulerWorkerRuntimeReceiptHandoff example")
    if record.get("scheduler_receipt_ref") != EXPECTED_SCHEDULER_REF:
        errors.append("scheduler_receipt_ref must point to the Foundation scheduler receipt ref")
    if record.get("distributed_lease_execution_receipt_ref") != EXPECTED_DISTRIBUTED_LEASE_EXECUTION_REF:
        errors.append("distributed_lease_execution_receipt_ref must point to the Foundation distributed lease execution ref")
    if record.get("worker_mesh_ref") != EXPECTED_WORKER_MESH_REF:
        errors.append("worker_mesh_ref must point to the WorkerMesh schema")
    if record.get("worker_failure_receipt_ref") != EXPECTED_WORKER_FAILURE_REF:
        errors.append("worker_failure_receipt_ref must point to the WorkerFailureReceipt schema")
    if record.get("scheduler_receipt_ref") != handoff.get("scheduler_receipt_ref"):
        errors.append("scheduler_receipt_ref must match handoff scheduler_receipt_ref")
    if record.get("distributed_lease_execution_receipt_ref") != handoff.get("distributed_lease_execution_receipt_ref"):
        errors.append("distributed_lease_execution_receipt_ref must match handoff distributed_lease_execution_receipt_ref")
    if record.get("worker_mesh_ref") != handoff.get("worker_mesh_ref"):
        errors.append("worker_mesh_ref must match handoff worker_mesh_ref")
    if record.get("worker_failure_receipt_ref") != handoff.get("worker_failure_receipt_ref"):
        errors.append("worker_failure_receipt_ref must match handoff worker_failure_receipt_ref")


def _validate_authority_scope(scope: Any, errors: list[str]) -> None:
    if not isinstance(scope, dict):
        errors.append("authority_scope must be an object")
        return
    if scope.get("foundation_dry_run_only") is not True:
        errors.append("authority_scope.foundation_dry_run_only must be true")
    if scope.get("scheduler_worker_receipt_emitter_dry_run") is not True:
        errors.append("authority_scope.scheduler_worker_receipt_emitter_dry_run must be true")
    for field_name in DENIED_AUTHORITY_FIELDS:
        if scope.get(field_name) is not False:
            errors.append(f"authority_scope.{field_name} must be false")
    if scope.get("mfidel_atomicity_preserved") is not True:
        errors.append("authority_scope.mfidel_atomicity_preserved must be true")


def _validate_dry_run_contract(contract: Any, handoff: dict[str, Any], errors: list[str]) -> None:
    if not isinstance(contract, dict):
        errors.append("dry_run_contract must be an object")
        return
    handoff_contract = handoff.get("scheduler_worker_contract", {})
    if contract.get("operation_family") != EXPECTED_OPERATION_FAMILY:
        errors.append("dry_run_contract.operation_family must be scheduler_worker_runtime_receipt_emitter_dry_run")
    if contract.get("dry_run_mode") != EXPECTED_DRY_RUN_MODE:
        errors.append("dry_run_contract.dry_run_mode must be EMITTER_DRY_RUN_ONLY")
    if contract.get("source_handoff_ref") != EXPECTED_HANDOFF_REF:
        errors.append("dry_run_contract.source_handoff_ref must point to the scheduler worker handoff example")
    _require_subset(contract, "required_source_receipt_refs", REQUIRED_SOURCE_RECEIPT_REFS, errors)
    _require_subset(contract, "required_runtime_gate_refs", REQUIRED_RUNTIME_GATE_REFS, errors)
    _require_subset(contract, "required_runtime_witness_refs", REQUIRED_RUNTIME_WITNESS_REFS, errors)
    _require_subset(contract, "validation_refs", REQUIRED_VALIDATION_REFS, errors)
    _require_subset(
        contract,
        "required_runtime_gate_refs",
        tuple(handoff_contract.get("required_admission_gate_refs", [])),
        errors,
    )
    obligations = contract.get("emission_obligations_checked")
    if not isinstance(obligations, list) or len(obligations) < 6:
        errors.append("emission_obligations_checked must list scheduler-worker emitter obligations")
    elif not any(isinstance(item, str) and "WorkerFailureReceipt" in item for item in obligations):
        errors.append("emission_obligations_checked must require WorkerFailureReceipt on failed or partial dispatch")


def _validate_simulated_emission_result(result: Any, errors: list[str]) -> None:
    if not isinstance(result, dict):
        errors.append("simulated_emission_result must be an object")
        return
    if result.get("result_state") != EXPECTED_RESULT_STATE:
        errors.append("simulated_emission_result.result_state must be DRY_RUN_RECORDED")
    if result.get("simulated_receipt_kind") != "future_scheduler_worker_runtime_receipt":
        errors.append("simulated_emission_result.simulated_receipt_kind must be future_scheduler_worker_runtime_receipt")
    if result.get("dry_run_receipt_recorded") is not True:
        errors.append("simulated_emission_result.dry_run_receipt_recorded must be true")
    if result.get("failure_receipt_path_bound") is not True:
        errors.append("simulated_emission_result.failure_receipt_path_bound must be true")
    if result.get("effect_reconciliation_required") is not True:
        errors.append("simulated_emission_result.effect_reconciliation_required must be true")
    for field_name in DENIED_RESULT_FIELDS:
        if result.get(field_name) is not False:
            errors.append(f"simulated_emission_result.{field_name} must be false")
    output_digest = result.get("output_digest")
    if not isinstance(output_digest, str) or not output_digest.startswith("sha256:"):
        errors.append("simulated_emission_result.output_digest must be a sha256 digest reference")


def _validate_admission_decision(decision: Any, errors: list[str]) -> None:
    if not isinstance(decision, dict):
        errors.append("admission_decision must be an object")
        return
    if decision.get("decision") != EXPECTED_ADMISSION_DECISION:
        errors.append("admission_decision.decision must be DISPATCH_BLOCKED_AWAITING_RUNTIME_EVIDENCE")
    if decision.get("runtime_dispatch_admitted") is not False:
        errors.append("admission_decision.runtime_dispatch_admitted must be false")
    if decision.get("worker_invocation_admitted") is not False:
        errors.append("admission_decision.worker_invocation_admitted must be false")
    if decision.get("terminal_closure_allowed") is not False:
        errors.append("admission_decision.terminal_closure_allowed must be false")
    _require_subset(decision, "remaining_denied_until_refs", REQUIRED_REMAINING_DENIED_UNTIL_REFS, errors)
    _require_subset(decision, "blocked_reason_refs", REQUIRED_BLOCKED_REASON_REFS, errors)


def _validate_receipt_refs(refs: Any, errors: list[str]) -> None:
    if not isinstance(refs, dict):
        errors.append("receipt_refs must be an object")
        return
    for field_name, expected_ref in REQUIRED_RECEIPT_REFS.items():
        if refs.get(field_name) != expected_ref:
            errors.append(f"receipt_refs.{field_name} must be {expected_ref}")


def _validate_contract_summary(record: dict[str, Any], errors: list[str]) -> None:
    contract = record.get("dry_run_contract")
    result = record.get("simulated_emission_result")
    decision = record.get("admission_decision")
    refs = record.get("receipt_refs")
    summary = record.get("contract_summary")
    if not isinstance(contract, dict) or not isinstance(result, dict) or not isinstance(decision, dict):
        errors.append("dry_run_contract, simulated_emission_result, and admission_decision must be objects")
        return
    if not isinstance(refs, dict) or not isinstance(summary, dict):
        errors.append("receipt_refs and contract_summary must be objects")
        return
    expected_counts = {
        "source_receipt_ref_count": _list_len(contract.get("required_source_receipt_refs")),
        "runtime_gate_ref_count": _list_len(contract.get("required_runtime_gate_refs")),
        "runtime_witness_ref_count": _list_len(contract.get("required_runtime_witness_refs")),
        "emission_obligation_count": _list_len(contract.get("emission_obligations_checked")),
        "validation_ref_count": _list_len(contract.get("validation_refs")),
        "remaining_denied_until_ref_count": _list_len(decision.get("remaining_denied_until_refs")),
        "blocked_reason_ref_count": _list_len(decision.get("blocked_reason_refs")),
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
    """Validate SchedulerWorkerRuntimeReceiptEmitterDryRun artifacts from the CLI."""

    parser = argparse.ArgumentParser(description="Validate SchedulerWorkerRuntimeReceiptEmitterDryRun contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--handoff", type=Path, default=DEFAULT_HANDOFF_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable receipt")
    args = parser.parse_args(argv)
    errors = validate_emitter_dry_run(args.schema, args.receipt, args.handoff)
    if args.json:
        print(
            json.dumps(
                {
                    "receipt_id": "scheduler_worker_runtime_receipt_emitter_dry_run_validation",
                    "schema_path": workspace_display_path(args.schema),
                    "receipt_path": workspace_display_path(args.receipt),
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
        print("[PASS] scheduler_worker_runtime_receipt_emitter_dry_run")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

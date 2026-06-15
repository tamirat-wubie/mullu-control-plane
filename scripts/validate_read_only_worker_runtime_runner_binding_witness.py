#!/usr/bin/env python3
"""Validate the ReadOnlyWorkerRuntimeRunnerBindingWitness contract.

Purpose: verify Foundation Mode evidence for future runtime runner registration
and runtime receipt schema binding without performing either action.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, schema validation helpers, and
ReadOnlyWorkerRuntimeReceiptEmitterDryRun validation.
Invariants:
  - Validation is read-only and deterministic.
  - The witness applies only to read_only_repo_inspection.
  - Runtime runner, dispatch endpoint, runtime emitter, and runtime receipt
    schema binding remain unperformed.
  - Dispatch remains blocked until live runner, schema binding, temporal lease,
    UAO, Phi_gov, and effect reconciliation evidence exists.
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

from scripts.validate_read_only_worker_binding import EXPECTED_WORKER_PATH  # noqa: E402
from scripts.validate_read_only_worker_rehearsal_receipt import EXPECTED_WORKER_ID  # noqa: E402
from scripts.validate_read_only_worker_runtime_receipt_emitter_dry_run import (  # noqa: E402
    DEFAULT_RECEIPT_PATH as DEFAULT_EMITTER_DRY_RUN_PATH,
    DEFAULT_SCHEMA_PATH as DEFAULT_EMITTER_DRY_RUN_SCHEMA_PATH,
    load_json_object as load_emitter_json_object,
    validate_emitter_dry_run_record,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "read_only_worker_runtime_runner_binding_witness.schema.json"
DEFAULT_RECEIPT_PATH = WORKSPACE_ROOT / "examples" / "read_only_worker_runtime_runner_binding_witness.foundation.json"
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:read-only-worker-runtime-runner-binding-witness:1"
EXPECTED_SCHEMA_TITLE = "Read-Only Worker Runtime Runner Binding Witness"
EXPECTED_RECEIPT_VERSION = "read_only_worker_runtime_runner_binding_witness.v1"
EXPECTED_EMITTER_DRY_RUN_REF = "examples/read_only_worker_runtime_receipt_emitter_dry_run.foundation.json"
EXPECTED_HANDOFF_REF = "examples/read_only_worker_runtime_receipt_handoff.foundation.json"
EXPECTED_BINDING_REF = "examples/read_only_worker_binding.foundation.json"
EXPECTED_PREFLIGHT_REF = "examples/read_only_worker_lease_preflight.foundation.json"
EXPECTED_REHEARSAL_REF = "examples/read_only_worker_rehearsal_receipt.foundation.json"
EXPECTED_OPERATION_FAMILY = "local_repo_inspection"
EXPECTED_REGISTRATION_MODE = "REGISTRATION_WITNESS_ONLY"
EXPECTED_SCHEMA_BINDING_MODE = "SCHEMA_BINDING_WITNESS_ONLY"
EXPECTED_ADMISSION_DECISION = "RUNTIME_BINDING_BLOCKED_AWAITING_LIVE_RUNNER_WITNESS"
REQUIRED_REGISTRATION_WITNESS_REFS = (
    "witness://runtime-runner/registration-contract-defined",
    "witness://dispatch-endpoint/registration-contract-defined",
    "witness://runtime-receipt-emitter/registration-contract-defined",
    "witness://runtime-runner/not-registered",
)
REQUIRED_SCHEMA_BINDING_WITNESS_REFS = (
    "witness://runtime-receipt-schema/binding-contract-defined",
    "witness://runtime-receipt-schema/not-bound",
    "witness://runtime-receipt-envelope/uao-ref-required",
    "witness://runtime-receipt-envelope/failure-receipt-path-required",
)
REQUIRED_REGISTRATION_VALIDATION_REFS = (
    "scripts/validate_read_only_worker_runtime_runner_binding_witness.py",
    "scripts/validate_read_only_worker_runtime_receipt_emitter_dry_run.py",
    "scripts/validate_read_only_worker_runtime_receipt_handoff.py",
    "scripts/validate_read_only_worker_binding.py",
)
REQUIRED_SCHEMA_BINDING_VALIDATION_REFS = (
    "scripts/validate_read_only_worker_runtime_runner_binding_witness.py",
    "scripts/validate_read_only_worker_runtime_receipt_emitter_dry_run.py",
    "scripts/validate_schemas.py",
    "scripts/validate_protocol_manifest.py",
)
REQUIRED_REMAINING_DENIED_UNTIL_REFS = (
    "evidence://live-runtime-runner-registration-witness",
    "evidence://live-dispatch-endpoint-registration-witness",
    "evidence://runtime-receipt-emitter-registration-witness",
    "evidence://runtime-receipt-schema-binding-witness",
    "evidence://active-temporal-lease-window",
    "evidence://uao-effect-admission",
    "evidence://phi-gov-dispatch-authorization",
)
REQUIRED_BLOCKED_REASON_REFS = (
    "blocked://runtime-runner/not-registered",
    "blocked://dispatch-endpoint/not-registered",
    "blocked://runtime-receipt-emitter/not-registered",
    "blocked://runtime-receipt-schema/not-bound",
    "blocked://temporal-lease/not-active",
    "blocked://phi-gov/dispatch-not-authorized",
    "blocked://effect-reconciliation/not-proven",
)
REQUIRED_RECEIPT_REFS = {
    "read_only_worker_runtime_runner_binding_witness_schema": (
        "schemas/read_only_worker_runtime_runner_binding_witness.schema.json"
    ),
    "read_only_worker_runtime_receipt_emitter_dry_run_schema": (
        "schemas/read_only_worker_runtime_receipt_emitter_dry_run.schema.json"
    ),
    "read_only_worker_runtime_receipt_handoff_schema": "schemas/read_only_worker_runtime_receipt_handoff.schema.json",
    "read_only_worker_binding_schema": "schemas/read_only_worker_binding.schema.json",
    "read_only_worker_lease_preflight_schema": "schemas/read_only_worker_lease_preflight.schema.json",
    "read_only_worker_rehearsal_receipt_schema": "schemas/read_only_worker_rehearsal_receipt.schema.json",
    "personal_assistant_console_read_model_schema": "schemas/personal_assistant_console_read_model.schema.json",
    "temporal_lease_window_receipt_schema": "schemas/temporal_lease_window_receipt.schema.json",
    "worker_failure_receipt_schema": "schemas/worker_failure_receipt.schema.json",
    "worker_mesh_schema": "schemas/worker_mesh.schema.json",
}
REQUIRED_EVIDENCE_REFS = (
    "schemas/read_only_worker_runtime_runner_binding_witness.schema.json",
    "examples/read_only_worker_runtime_runner_binding_witness.foundation.json",
    "scripts/validate_read_only_worker_runtime_runner_binding_witness.py",
    "tests/test_validate_read_only_worker_runtime_runner_binding_witness.py",
    "schemas/read_only_worker_runtime_receipt_emitter_dry_run.schema.json",
    EXPECTED_EMITTER_DRY_RUN_REF,
)
DENIED_AUTHORITY_FIELDS = (
    "runtime_runner_registration_performed",
    "dispatch_endpoint_registration_performed",
    "runtime_receipt_emitter_registration_performed",
    "runtime_receipt_schema_binding_performed",
    "runtime_dispatch_allowed",
    "external_network_allowed",
    "secret_access_allowed",
    "filesystem_write_allowed",
    "connector_authority_allowed",
    "terminal_closure_allowed",
    "success_claim_allowed",
)


class ReadOnlyWorkerRuntimeRunnerBindingWitnessError(ValueError):
    """Raised when a runtime runner binding witness artifact cannot load."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {json_path}")
    if not json_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ReadOnlyWorkerRuntimeRunnerBindingWitnessError(f"{label} must be a JSON object")
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
            "authority_scope",
            "registration_witness_contract",
            "schema_binding_witness_contract",
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


def validate_runner_binding_witness_record(
    record: Any,
    schema: dict[str, Any] | None = None,
    emitter_dry_run: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one runner binding witness."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("read-only worker runtime runner binding witness must be a JSON object")
        return errors

    emitter_payload = emitter_dry_run or load_emitter_json_object(
        DEFAULT_EMITTER_DRY_RUN_PATH,
        "ReadOnlyWorkerRuntimeReceiptEmitterDryRun",
    )
    emitter_schema = _load_schema(DEFAULT_EMITTER_DRY_RUN_SCHEMA_PATH)
    errors.extend(f"emitter dry-run: {error}" for error in validate_emitter_dry_run_record(emitter_payload, emitter_schema))

    _validate_top_level_refs(record, emitter_payload, errors)
    _validate_authority_scope(record.get("authority_scope"), errors)
    _validate_registration_contract(record.get("registration_witness_contract"), emitter_payload, errors)
    _validate_schema_binding_contract(record.get("schema_binding_witness_contract"), errors)
    _validate_admission_decision(record.get("admission_decision"), errors)
    _validate_receipt_refs(record.get("receipt_refs"), errors)
    _validate_contract_summary(record, errors)
    _require_subset(record, "evidence_refs", REQUIRED_EVIDENCE_REFS, errors)
    return errors


def validate_runner_binding_witness(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
    emitter_dry_run_path: Path = DEFAULT_EMITTER_DRY_RUN_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode witness."""

    schema = _load_schema(schema_path)
    receipt = load_json_object(receipt_path, "ReadOnlyWorkerRuntimeRunnerBindingWitness")
    emitter_dry_run = load_emitter_json_object(emitter_dry_run_path, "ReadOnlyWorkerRuntimeReceiptEmitterDryRun")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_runner_binding_witness_record(receipt, schema, emitter_dry_run))
    return errors


def build_mutated_runner_binding_witness(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default witness receipt."""

    receipt = load_json_object(DEFAULT_RECEIPT_PATH, "ReadOnlyWorkerRuntimeRunnerBindingWitness")
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


def _validate_top_level_refs(record: dict[str, Any], emitter: dict[str, Any], errors: list[str]) -> None:
    if record.get("receipt_version") != EXPECTED_RECEIPT_VERSION:
        errors.append("receipt_version must match read_only_worker_runtime_runner_binding_witness.v1")
    if record.get("emitter_dry_run_ref") != EXPECTED_EMITTER_DRY_RUN_REF:
        errors.append("emitter_dry_run_ref must point to the Foundation emitter dry-run example")
    if record.get("handoff_ref") != EXPECTED_HANDOFF_REF:
        errors.append("handoff_ref must point to the Foundation runtime receipt handoff example")
    if record.get("binding_ref") != EXPECTED_BINDING_REF:
        errors.append("binding_ref must point to the Foundation ReadOnlyWorkerBinding example")
    if record.get("lease_preflight_ref") != EXPECTED_PREFLIGHT_REF:
        errors.append("lease_preflight_ref must point to the Foundation ReadOnlyWorkerLeasePreflight example")
    if record.get("rehearsal_receipt_ref") != EXPECTED_REHEARSAL_REF:
        errors.append("rehearsal_receipt_ref must point to the Foundation ReadOnlyWorkerRehearsalReceipt example")
    if record.get("selected_worker_path") != EXPECTED_WORKER_PATH:
        errors.append("selected_worker_path must be read_only_repo_inspection")
    if record.get("selected_worker_path") != emitter.get("selected_worker_path"):
        errors.append("runner binding witness selected_worker_path must match emitter dry-run selected_worker_path")


def _validate_authority_scope(scope: Any, errors: list[str]) -> None:
    if not isinstance(scope, dict):
        errors.append("authority_scope must be an object")
        return
    if scope.get("read_only") is not True:
        errors.append("authority_scope.read_only must be true")
    if scope.get("foundation_witness_only") is not True:
        errors.append("authority_scope.foundation_witness_only must be true")
    for field_name in DENIED_AUTHORITY_FIELDS:
        if scope.get(field_name) is not False:
            errors.append(f"authority_scope.{field_name} must be false")
    if scope.get("mfidel_atomicity_preserved") is not True:
        errors.append("authority_scope.mfidel_atomicity_preserved must be true")


def _validate_registration_contract(contract: Any, emitter: dict[str, Any], errors: list[str]) -> None:
    if not isinstance(contract, dict):
        errors.append("registration_witness_contract must be an object")
        return
    dry_run_contract = emitter.get("dry_run_contract", {})
    if contract.get("worker_id") != EXPECTED_WORKER_ID:
        errors.append("registration_witness_contract.worker_id must select worker_local_read_only_repo_inspection")
    if contract.get("worker_id") != dry_run_contract.get("worker_id"):
        errors.append("registration_witness_contract.worker_id must match emitter dry-run worker_id")
    if contract.get("capability") != EXPECTED_WORKER_PATH:
        errors.append("registration_witness_contract.capability must be read_only_repo_inspection")
    if contract.get("operation_family") != EXPECTED_OPERATION_FAMILY:
        errors.append("registration_witness_contract.operation_family must be local_repo_inspection")
    if contract.get("witness_mode") != EXPECTED_REGISTRATION_MODE:
        errors.append("registration_witness_contract.witness_mode must be REGISTRATION_WITNESS_ONLY")
    _require_subset(contract, "required_registration_witness_refs", REQUIRED_REGISTRATION_WITNESS_REFS, errors)
    _require_subset(contract, "validation_refs", REQUIRED_REGISTRATION_VALIDATION_REFS, errors)
    obligations = contract.get("registration_obligations_checked")
    if not isinstance(obligations, list) or len(obligations) < 5:
        errors.append("registration_obligations_checked must list future registration obligations")
    elif not any(isinstance(item, str) and "WorkerFailureReceipt" in item for item in obligations):
        errors.append("registration_obligations_checked must require WorkerFailureReceipt on failed or partial dispatch")


def _validate_schema_binding_contract(contract: Any, errors: list[str]) -> None:
    if not isinstance(contract, dict):
        errors.append("schema_binding_witness_contract must be an object")
        return
    if contract.get("runtime_receipt_kind") != "future_worker_runtime_receipt":
        errors.append("schema_binding_witness_contract.runtime_receipt_kind must be future_worker_runtime_receipt")
    if contract.get("schema_binding_mode") != EXPECTED_SCHEMA_BINDING_MODE:
        errors.append("schema_binding_witness_contract.schema_binding_mode must be SCHEMA_BINDING_WITNESS_ONLY")
    if contract.get("schema_candidate_ref") != "candidate://schema/future-worker-runtime-receipt":
        errors.append("schema_binding_witness_contract.schema_candidate_ref must point to the future runtime receipt candidate")
    if contract.get("source_dry_run_ref") != EXPECTED_EMITTER_DRY_RUN_REF:
        errors.append("schema_binding_witness_contract.source_dry_run_ref must point to the emitter dry-run example")
    _require_subset(contract, "required_schema_binding_witness_refs", REQUIRED_SCHEMA_BINDING_WITNESS_REFS, errors)
    _require_subset(contract, "validation_refs", REQUIRED_SCHEMA_BINDING_VALIDATION_REFS, errors)
    obligations = contract.get("schema_binding_obligations_checked")
    if not isinstance(obligations, list) or len(obligations) < 5:
        errors.append("schema_binding_obligations_checked must list future schema binding obligations")
    elif not any(isinstance(item, str) and "Mfidel atomicity" in item for item in obligations):
        errors.append("schema_binding_obligations_checked must preserve Mfidel atomicity")


def _validate_admission_decision(decision: Any, errors: list[str]) -> None:
    if not isinstance(decision, dict):
        errors.append("admission_decision must be an object")
        return
    if decision.get("decision") != EXPECTED_ADMISSION_DECISION:
        errors.append("admission_decision.decision must be RUNTIME_BINDING_BLOCKED_AWAITING_LIVE_RUNNER_WITNESS")
    for field_name in ("runtime_runner_admitted", "runtime_receipt_schema_bound", "runtime_dispatch_admitted", "terminal_closure_allowed"):
        if decision.get(field_name) is not False:
            errors.append(f"admission_decision.{field_name} must be false")
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
    registration = record.get("registration_witness_contract")
    schema_binding = record.get("schema_binding_witness_contract")
    decision = record.get("admission_decision")
    refs = record.get("receipt_refs")
    summary = record.get("contract_summary")
    if not all(isinstance(value, dict) for value in (registration, schema_binding, decision, refs, summary)):
        errors.append("registration, schema binding, admission, receipt refs, and summary must be objects")
        return
    expected_counts = {
        "registration_witness_ref_count": _list_len(registration.get("required_registration_witness_refs")),
        "registration_obligation_count": _list_len(registration.get("registration_obligations_checked")),
        "registration_validation_ref_count": _list_len(registration.get("validation_refs")),
        "schema_binding_witness_ref_count": _list_len(schema_binding.get("required_schema_binding_witness_refs")),
        "schema_binding_obligation_count": _list_len(schema_binding.get("schema_binding_obligations_checked")),
        "schema_binding_validation_ref_count": _list_len(schema_binding.get("validation_refs")),
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
    """Validate ReadOnlyWorkerRuntimeRunnerBindingWitness artifacts from the CLI."""

    parser = argparse.ArgumentParser(description="Validate ReadOnlyWorkerRuntimeRunnerBindingWitness contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--emitter-dry-run", type=Path, default=DEFAULT_EMITTER_DRY_RUN_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable receipt")
    args = parser.parse_args(argv)
    errors = validate_runner_binding_witness(args.schema, args.receipt, args.emitter_dry_run)
    if args.json:
        print(
            json.dumps(
                {
                    "receipt_id": "read_only_worker_runtime_runner_binding_witness_validation",
                    "schema_path": workspace_display_path(args.schema),
                    "receipt_path": workspace_display_path(args.receipt),
                    "emitter_dry_run_path": workspace_display_path(args.emitter_dry_run),
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
        print("[PASS] read_only_worker_runtime_runner_binding_witness")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

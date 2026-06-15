#!/usr/bin/env python3
"""Validate the ReadOnlyWorkerRuntimeReceiptCandidate contract.

Purpose: verify the Foundation Mode candidate envelope for a future
read_only_repo_inspection runtime receipt without binding or emitting that
runtime receipt.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, schema validation helpers,
ReadOnlyWorkerRuntimeRunnerBindingWitness, and
ReadOnlyWorkerRuntimeReceiptEmitterDryRun validation.
Invariants:
  - Validation is read-only and deterministic.
  - The candidate applies only to read_only_repo_inspection.
  - Runtime runner, dispatch endpoint, emitter, schema binding, runtime
    dispatch, and runtime receipt emission remain unperformed.
  - Raw output, secret material, external effects, filesystem writes,
    connector calls, success claims, and terminal closure remain denied.
  - WorkerFailureReceipt and effect reconciliation stay mandatory for future
    failed, partial, or effect-bearing runtime evidence.
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
from scripts.validate_read_only_worker_runtime_runner_binding_witness import (  # noqa: E402
    DEFAULT_RECEIPT_PATH as DEFAULT_RUNNER_BINDING_WITNESS_PATH,
    DEFAULT_SCHEMA_PATH as DEFAULT_RUNNER_BINDING_WITNESS_SCHEMA_PATH,
    load_json_object as load_runner_binding_json_object,
    validate_runner_binding_witness_record,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "read_only_worker_runtime_receipt_candidate.schema.json"
DEFAULT_RECEIPT_PATH = WORKSPACE_ROOT / "examples" / "read_only_worker_runtime_receipt_candidate.foundation.json"
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:read-only-worker-runtime-receipt-candidate:1"
EXPECTED_SCHEMA_TITLE = "Read-Only Worker Runtime Receipt Candidate"
EXPECTED_RECEIPT_VERSION = "read_only_worker_runtime_receipt_candidate.v1"
EXPECTED_RUNNER_BINDING_WITNESS_REF = "examples/read_only_worker_runtime_runner_binding_witness.foundation.json"
EXPECTED_EMITTER_DRY_RUN_REF = "examples/read_only_worker_runtime_receipt_emitter_dry_run.foundation.json"
EXPECTED_HANDOFF_REF = "examples/read_only_worker_runtime_receipt_handoff.foundation.json"
EXPECTED_BINDING_REF = "examples/read_only_worker_binding.foundation.json"
EXPECTED_PREFLIGHT_REF = "examples/read_only_worker_lease_preflight.foundation.json"
EXPECTED_REHEARSAL_REF = "examples/read_only_worker_rehearsal_receipt.foundation.json"
EXPECTED_OPERATION_FAMILY = "local_repo_inspection"
EXPECTED_CANDIDATE_MODE = "RUNTIME_RECEIPT_CANDIDATE_ONLY"
EXPECTED_EXECUTION_STATE = "NOT_EXECUTED_CANDIDATE_ONLY"
EXPECTED_ADMISSION_DECISION = "RUNTIME_RECEIPT_CANDIDATE_BLOCKED_AWAITING_SCHEMA_BINDING_AND_LIVE_RUNNER"
REQUIRED_SOURCE_RECEIPT_REFS = (
    EXPECTED_RUNNER_BINDING_WITNESS_REF,
    EXPECTED_EMITTER_DRY_RUN_REF,
    EXPECTED_HANDOFF_REF,
    EXPECTED_BINDING_REF,
    EXPECTED_PREFLIGHT_REF,
    EXPECTED_REHEARSAL_REF,
)
REQUIRED_GOVERNANCE_GATE_REFS = (
    "gate://runtime-runner-registration",
    "gate://dispatch-endpoint-registration",
    "gate://runtime-receipt-emitter-registration",
    "gate://runtime-receipt-schema-binding",
    "gate://temporal-lease-active",
    "gate://uao-effect-admission",
    "gate://phi-gov-dispatch-authorization",
    "gate://worker-failure-receipt-on-error",
    "gate://effect-reconciliation-before-terminal-closure",
)
REQUIRED_RUNTIME_EVIDENCE_REFS = (
    "evidence://live-runtime-runner-registration-witness",
    "evidence://live-dispatch-endpoint-registration-witness",
    "evidence://runtime-receipt-emitter-registration-witness",
    "evidence://runtime-receipt-schema-binding-witness",
    "evidence://active-temporal-lease-window",
    "evidence://uao-effect-admission",
    "evidence://phi-gov-dispatch-authorization",
    "evidence://effect-reconciliation-passed",
)
REQUIRED_VALIDATION_REFS = (
    "scripts/validate_read_only_worker_runtime_receipt_candidate.py",
    "scripts/validate_read_only_worker_runtime_runner_binding_witness.py",
    "scripts/validate_read_only_worker_runtime_receipt_emitter_dry_run.py",
    "scripts/validate_schemas.py",
    "scripts/validate_protocol_manifest.py",
)
REQUIRED_REMAINING_DENIED_UNTIL_REFS = REQUIRED_RUNTIME_EVIDENCE_REFS
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
    "read_only_worker_runtime_receipt_candidate_schema": "schemas/read_only_worker_runtime_receipt_candidate.schema.json",
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
    "temporal_lease_window_receipt_schema": "schemas/temporal_lease_window_receipt.schema.json",
    "worker_failure_receipt_schema": "schemas/worker_failure_receipt.schema.json",
    "worker_mesh_schema": "schemas/worker_mesh.schema.json",
    "universal_action_orchestration_schema": "schemas/universal_action_orchestration.schema.json",
}
REQUIRED_EVIDENCE_REFS = (
    "schemas/read_only_worker_runtime_receipt_candidate.schema.json",
    "examples/read_only_worker_runtime_receipt_candidate.foundation.json",
    "scripts/validate_read_only_worker_runtime_receipt_candidate.py",
    "tests/test_validate_read_only_worker_runtime_receipt_candidate.py",
    "schemas/read_only_worker_runtime_runner_binding_witness.schema.json",
    EXPECTED_RUNNER_BINDING_WITNESS_REF,
    "schemas/read_only_worker_runtime_receipt_emitter_dry_run.schema.json",
    EXPECTED_EMITTER_DRY_RUN_REF,
)
ENVELOPE_TRUE_FIELDS = (
    "uao_ref_required",
    "phi_gov_decision_ref_required",
    "causal_decision_trace_ref_required",
    "temporal_lease_window_receipt_ref_required",
    "runtime_runner_registration_witness_ref_required",
    "runtime_receipt_schema_binding_witness_ref_required",
    "worker_failure_receipt_ref_required_on_error",
    "effect_reconciliation_ref_required",
    "receipt_store_ref_required",
)
FAILURE_POLICY_TRUE_FIELDS = (
    "worker_failure_receipt_required",
    "partial_effects_must_be_listed",
    "unknown_effects_block_terminal_closure",
    "rollback_refs_required",
    "recovery_refs_required",
    "success_claim_blocked_on_failure",
    "mfidel_atomicity_preserved",
)
DENIED_AUTHORITY_FIELDS = (
    "runtime_runner_registration_performed",
    "dispatch_endpoint_registration_performed",
    "runtime_receipt_emitter_registration_performed",
    "runtime_receipt_schema_binding_performed",
    "runtime_dispatch_allowed",
    "runtime_receipt_emission_allowed",
    "external_network_allowed",
    "secret_access_allowed",
    "filesystem_write_allowed",
    "connector_authority_allowed",
    "terminal_closure_allowed",
    "success_claim_allowed",
)
DENIED_EXECUTION_FIELDS = (
    "runtime_dispatch_started",
    "worker_invoked",
    "runtime_receipt_emitted",
    "worker_mesh_dispatch_receipt_emitted",
    "raw_output_included",
    "raw_secret_material_included",
    "external_effects_observed",
    "filesystem_writes_observed",
    "connector_calls_observed",
    "terminal_closure",
    "success_claim_allowed",
)


class ReadOnlyWorkerRuntimeReceiptCandidateError(ValueError):
    """Raised when a runtime receipt candidate artifact cannot load."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {json_path}")
    if not json_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ReadOnlyWorkerRuntimeReceiptCandidateError(f"{label} must be a JSON object")
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
            "runtime_receipt_candidate_contract",
            "candidate_receipt_envelope",
            "candidate_execution_summary",
            "candidate_failure_policy",
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


def validate_runtime_receipt_candidate_record(
    record: Any,
    schema: dict[str, Any] | None = None,
    runner_binding_witness: dict[str, Any] | None = None,
    emitter_dry_run: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one candidate receipt."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("read-only worker runtime receipt candidate must be a JSON object")
        return errors

    runner_payload = runner_binding_witness or load_runner_binding_json_object(
        DEFAULT_RUNNER_BINDING_WITNESS_PATH,
        "ReadOnlyWorkerRuntimeRunnerBindingWitness",
    )
    runner_schema = _load_schema(DEFAULT_RUNNER_BINDING_WITNESS_SCHEMA_PATH)
    errors.extend(
        f"runner binding witness: {error}"
        for error in validate_runner_binding_witness_record(runner_payload, runner_schema)
    )

    emitter_payload = emitter_dry_run or load_emitter_json_object(
        DEFAULT_EMITTER_DRY_RUN_PATH,
        "ReadOnlyWorkerRuntimeReceiptEmitterDryRun",
    )
    emitter_schema = _load_schema(DEFAULT_EMITTER_DRY_RUN_SCHEMA_PATH)
    errors.extend(
        f"emitter dry-run: {error}"
        for error in validate_emitter_dry_run_record(emitter_payload, emitter_schema)
    )

    _validate_top_level_refs(record, runner_payload, emitter_payload, errors)
    _validate_authority_scope(record.get("authority_scope"), errors)
    _validate_candidate_contract(record.get("runtime_receipt_candidate_contract"), runner_payload, emitter_payload, errors)
    _validate_candidate_receipt_envelope(record.get("candidate_receipt_envelope"), errors)
    _validate_candidate_execution_summary(record.get("candidate_execution_summary"), emitter_payload, errors)
    _validate_candidate_failure_policy(record.get("candidate_failure_policy"), errors)
    _validate_admission_decision(record.get("admission_decision"), errors)
    _validate_receipt_refs(record.get("receipt_refs"), errors)
    _validate_contract_summary(record, errors)
    _require_subset(record, "evidence_refs", REQUIRED_EVIDENCE_REFS, errors)
    return errors


def validate_runtime_receipt_candidate(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
    runner_binding_witness_path: Path = DEFAULT_RUNNER_BINDING_WITNESS_PATH,
    emitter_dry_run_path: Path = DEFAULT_EMITTER_DRY_RUN_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode candidate."""

    schema = _load_schema(schema_path)
    receipt = load_json_object(receipt_path, "ReadOnlyWorkerRuntimeReceiptCandidate")
    runner_binding_witness = load_runner_binding_json_object(
        runner_binding_witness_path,
        "ReadOnlyWorkerRuntimeRunnerBindingWitness",
    )
    emitter_dry_run = load_emitter_json_object(emitter_dry_run_path, "ReadOnlyWorkerRuntimeReceiptEmitterDryRun")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_runtime_receipt_candidate_record(receipt, schema, runner_binding_witness, emitter_dry_run))
    return errors


def build_mutated_runtime_receipt_candidate(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default candidate receipt."""

    receipt = load_json_object(DEFAULT_RECEIPT_PATH, "ReadOnlyWorkerRuntimeReceiptCandidate")
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


def _validate_top_level_refs(
    record: dict[str, Any],
    runner_binding_witness: dict[str, Any],
    emitter_dry_run: dict[str, Any],
    errors: list[str],
) -> None:
    if record.get("receipt_version") != EXPECTED_RECEIPT_VERSION:
        errors.append("receipt_version must match read_only_worker_runtime_receipt_candidate.v1")
    expected_refs = {
        "runner_binding_witness_ref": EXPECTED_RUNNER_BINDING_WITNESS_REF,
        "emitter_dry_run_ref": EXPECTED_EMITTER_DRY_RUN_REF,
        "handoff_ref": EXPECTED_HANDOFF_REF,
        "binding_ref": EXPECTED_BINDING_REF,
        "lease_preflight_ref": EXPECTED_PREFLIGHT_REF,
        "rehearsal_receipt_ref": EXPECTED_REHEARSAL_REF,
    }
    for field_name, expected_ref in expected_refs.items():
        if record.get(field_name) != expected_ref:
            errors.append(f"{field_name} must be {expected_ref}")
    if record.get("selected_worker_path") != EXPECTED_WORKER_PATH:
        errors.append("selected_worker_path must be read_only_repo_inspection")
    if record.get("selected_worker_path") != runner_binding_witness.get("selected_worker_path"):
        errors.append("runtime receipt candidate selected_worker_path must match runner binding witness")
    if record.get("selected_worker_path") != emitter_dry_run.get("selected_worker_path"):
        errors.append("runtime receipt candidate selected_worker_path must match emitter dry-run")


def _validate_authority_scope(scope: Any, errors: list[str]) -> None:
    if not isinstance(scope, dict):
        errors.append("authority_scope must be an object")
        return
    if scope.get("read_only") is not True:
        errors.append("authority_scope.read_only must be true")
    if scope.get("foundation_candidate_only") is not True:
        errors.append("authority_scope.foundation_candidate_only must be true")
    for field_name in DENIED_AUTHORITY_FIELDS:
        if scope.get(field_name) is not False:
            errors.append(f"authority_scope.{field_name} must be false")
    if scope.get("mfidel_atomicity_preserved") is not True:
        errors.append("authority_scope.mfidel_atomicity_preserved must be true")


def _validate_candidate_contract(
    contract: Any,
    runner_binding_witness: dict[str, Any],
    emitter_dry_run: dict[str, Any],
    errors: list[str],
) -> None:
    if not isinstance(contract, dict):
        errors.append("runtime_receipt_candidate_contract must be an object")
        return
    runner_contract = runner_binding_witness.get("registration_witness_contract", {})
    emitter_contract = emitter_dry_run.get("dry_run_contract", {})
    if contract.get("worker_id") != EXPECTED_WORKER_ID:
        errors.append("runtime_receipt_candidate_contract.worker_id must select worker_local_read_only_repo_inspection")
    for label, source_contract in (("runner binding witness", runner_contract), ("emitter dry-run", emitter_contract)):
        if contract.get("worker_id") != source_contract.get("worker_id"):
            errors.append(f"runtime_receipt_candidate_contract.worker_id must match {label} worker_id")
    if contract.get("capability") != EXPECTED_WORKER_PATH:
        errors.append("runtime_receipt_candidate_contract.capability must be read_only_repo_inspection")
    if contract.get("operation_family") != EXPECTED_OPERATION_FAMILY:
        errors.append("runtime_receipt_candidate_contract.operation_family must be local_repo_inspection")
    if contract.get("candidate_mode") != EXPECTED_CANDIDATE_MODE:
        errors.append("runtime_receipt_candidate_contract.candidate_mode must be RUNTIME_RECEIPT_CANDIDATE_ONLY")
    if contract.get("source_runner_binding_witness_ref") != EXPECTED_RUNNER_BINDING_WITNESS_REF:
        errors.append("runtime_receipt_candidate_contract.source_runner_binding_witness_ref is invalid")
    if contract.get("source_emitter_dry_run_ref") != EXPECTED_EMITTER_DRY_RUN_REF:
        errors.append("runtime_receipt_candidate_contract.source_emitter_dry_run_ref is invalid")
    _require_subset(contract, "required_source_receipt_refs", REQUIRED_SOURCE_RECEIPT_REFS, errors)
    _require_subset(contract, "required_governance_gate_refs", REQUIRED_GOVERNANCE_GATE_REFS, errors)
    _require_subset(contract, "required_runtime_evidence_refs", REQUIRED_RUNTIME_EVIDENCE_REFS, errors)
    _require_subset(contract, "validation_refs", REQUIRED_VALIDATION_REFS, errors)
    obligations = contract.get("candidate_obligations_checked")
    if not isinstance(obligations, list) or len(obligations) < 7:
        errors.append("candidate_obligations_checked must list future runtime receipt obligations")
    elif not any(isinstance(item, str) and "WorkerFailureReceipt" in item for item in obligations):
        errors.append("candidate_obligations_checked must require WorkerFailureReceipt on failed or partial dispatch")
    elif not any(isinstance(item, str) and "Mfidel atomicity" in item for item in obligations):
        errors.append("candidate_obligations_checked must preserve Mfidel atomicity")


def _validate_candidate_receipt_envelope(envelope: Any, errors: list[str]) -> None:
    if not isinstance(envelope, dict):
        errors.append("candidate_receipt_envelope must be an object")
        return
    for field_name in ENVELOPE_TRUE_FIELDS:
        if envelope.get(field_name) is not True:
            errors.append(f"candidate_receipt_envelope.{field_name} must be true")
    if envelope.get("raw_output_policy") != "DIGEST_ONLY_NO_RAW_OUTPUT":
        errors.append("candidate_receipt_envelope.raw_output_policy must be DIGEST_ONLY_NO_RAW_OUTPUT")


def _validate_candidate_execution_summary(
    summary: Any,
    emitter_dry_run: dict[str, Any],
    errors: list[str],
) -> None:
    if not isinstance(summary, dict):
        errors.append("candidate_execution_summary must be an object")
        return
    if summary.get("execution_state") != EXPECTED_EXECUTION_STATE:
        errors.append("candidate_execution_summary.execution_state must be NOT_EXECUTED_CANDIDATE_ONLY")
    if summary.get("failure_receipt_path_bound") is not True:
        errors.append("candidate_execution_summary.failure_receipt_path_bound must be true")
    if summary.get("effect_reconciliation_required") is not True:
        errors.append("candidate_execution_summary.effect_reconciliation_required must be true")
    if summary.get("output_digest_only") is not True:
        errors.append("candidate_execution_summary.output_digest_only must be true")
    for field_name in DENIED_EXECUTION_FIELDS:
        if summary.get(field_name) is not False:
            errors.append(f"candidate_execution_summary.{field_name} must be false")
    output_digest = summary.get("output_digest")
    if not isinstance(output_digest, str) or not output_digest.startswith("sha256:"):
        errors.append("candidate_execution_summary.output_digest must be a sha256 digest reference")
    emitter_result = emitter_dry_run.get("simulated_emission_result", {})
    if isinstance(emitter_result, dict) and output_digest != emitter_result.get("output_digest"):
        errors.append("candidate_execution_summary.output_digest must match emitter dry-run output_digest")


def _validate_candidate_failure_policy(policy: Any, errors: list[str]) -> None:
    if not isinstance(policy, dict):
        errors.append("candidate_failure_policy must be an object")
        return
    for field_name in FAILURE_POLICY_TRUE_FIELDS:
        if policy.get(field_name) is not True:
            errors.append(f"candidate_failure_policy.{field_name} must be true")


def _validate_admission_decision(decision: Any, errors: list[str]) -> None:
    if not isinstance(decision, dict):
        errors.append("admission_decision must be an object")
        return
    if decision.get("decision") != EXPECTED_ADMISSION_DECISION:
        errors.append("admission_decision.decision must be RUNTIME_RECEIPT_CANDIDATE_BLOCKED_AWAITING_SCHEMA_BINDING_AND_LIVE_RUNNER")
    if decision.get("candidate_defined") is not True:
        errors.append("admission_decision.candidate_defined must be true")
    for field_name in (
        "runtime_receipt_schema_bound",
        "runtime_receipt_emission_admitted",
        "runtime_dispatch_admitted",
        "terminal_closure_allowed",
    ):
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
    contract = record.get("runtime_receipt_candidate_contract")
    envelope = record.get("candidate_receipt_envelope")
    policy = record.get("candidate_failure_policy")
    decision = record.get("admission_decision")
    refs = record.get("receipt_refs")
    summary = record.get("contract_summary")
    if not all(isinstance(value, dict) for value in (contract, envelope, policy, decision, refs, summary)):
        errors.append("candidate contract, envelope, policy, decision, refs, and summary must be objects")
        return
    expected_counts = {
        "source_receipt_ref_count": _list_len(contract.get("required_source_receipt_refs")),
        "governance_gate_ref_count": _list_len(contract.get("required_governance_gate_refs")),
        "runtime_evidence_ref_count": _list_len(contract.get("required_runtime_evidence_refs")),
        "candidate_obligation_count": _list_len(contract.get("candidate_obligations_checked")),
        "validation_ref_count": _list_len(contract.get("validation_refs")),
        "envelope_required_ref_count": sum(1 for field_name in ENVELOPE_TRUE_FIELDS if envelope.get(field_name) is True),
        "failure_policy_required_count": sum(1 for field_name in FAILURE_POLICY_TRUE_FIELDS if policy.get(field_name) is True),
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
    """Validate ReadOnlyWorkerRuntimeReceiptCandidate artifacts from the CLI."""

    parser = argparse.ArgumentParser(description="Validate ReadOnlyWorkerRuntimeReceiptCandidate contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--runner-binding-witness", type=Path, default=DEFAULT_RUNNER_BINDING_WITNESS_PATH)
    parser.add_argument("--emitter-dry-run", type=Path, default=DEFAULT_EMITTER_DRY_RUN_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable receipt")
    args = parser.parse_args(argv)
    errors = validate_runtime_receipt_candidate(
        args.schema,
        args.receipt,
        args.runner_binding_witness,
        args.emitter_dry_run,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "receipt_id": "read_only_worker_runtime_receipt_candidate_validation",
                    "schema_path": workspace_display_path(args.schema),
                    "receipt_path": workspace_display_path(args.receipt),
                    "runner_binding_witness_path": workspace_display_path(args.runner_binding_witness),
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
        print("[PASS] read_only_worker_runtime_receipt_candidate")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

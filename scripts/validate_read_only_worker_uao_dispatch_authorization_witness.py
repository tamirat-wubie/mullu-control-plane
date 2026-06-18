#!/usr/bin/env python3
"""Validate the ReadOnlyWorkerUaoDispatchAuthorizationWitness contract.

Purpose: verify Foundation Mode witness evidence for future Universal Action
Orchestration dispatch authorization before read_only_repo_inspection runtime
dispatch without authorizing UAO, authorizing Phi_gov, or admitting dispatch.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, schema validation helpers,
ReadOnlyWorkerRuntimeDispatchAdmissionWitness validation, and
ReadOnlyWorkerActiveRuntimeLeaseAdmissionWitness validation.
Invariants:
  - Validation is read-only and deterministic.
  - The witness applies only to read_only_repo_inspection.
  - UAO dispatch authorization, Phi_gov dispatch authorization, runtime dispatch
    admission, runtime dispatch, worker invocation, receipt emission, receipt
    append, success claims, and terminal closure remain unperformed.
  - Future dispatch still requires UAO request evidence, effect-bearing
    classification, no-bypass proof, policy allow decision, active runtime lease
    admission, Phi_gov authorization, WorkerFailureReceipt obligations, and
    effect reconciliation.
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
from scripts.validate_read_only_worker_active_runtime_lease_admission_witness import (  # noqa: E402
    DEFAULT_RECEIPT_PATH as DEFAULT_ACTIVE_RUNTIME_LEASE_ADMISSION_WITNESS_PATH,
    DEFAULT_SCHEMA_PATH as DEFAULT_ACTIVE_RUNTIME_LEASE_ADMISSION_WITNESS_SCHEMA_PATH,
    load_json_object as load_active_runtime_lease_admission_json_object,
    validate_active_runtime_lease_admission_witness_record,
)
from scripts.validate_read_only_worker_rehearsal_receipt import EXPECTED_WORKER_ID  # noqa: E402
from scripts.validate_read_only_worker_runtime_dispatch_admission_witness import (  # noqa: E402
    DEFAULT_RECEIPT_PATH as DEFAULT_RUNTIME_DISPATCH_ADMISSION_WITNESS_PATH,
    DEFAULT_SCHEMA_PATH as DEFAULT_RUNTIME_DISPATCH_ADMISSION_WITNESS_SCHEMA_PATH,
    load_json_object as load_runtime_dispatch_admission_json_object,
    validate_runtime_dispatch_admission_witness_record,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = (
    WORKSPACE_ROOT
    / "schemas"
    / "read_only_worker_uao_dispatch_authorization_witness.schema.json"
)
DEFAULT_RECEIPT_PATH = (
    WORKSPACE_ROOT
    / "examples"
    / "read_only_worker_uao_dispatch_authorization_witness.foundation.json"
)
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:read-only-worker-uao-dispatch-authorization-witness:1"
EXPECTED_SCHEMA_TITLE = "Read-Only Worker UAO Dispatch Authorization Witness"
EXPECTED_RECEIPT_VERSION = "read_only_worker_uao_dispatch_authorization_witness.v1"
EXPECTED_RUNTIME_DISPATCH_ADMISSION_WITNESS_REF = (
    "examples/read_only_worker_runtime_dispatch_admission_witness.foundation.json"
)
EXPECTED_ACTIVE_RUNTIME_LEASE_ADMISSION_WITNESS_REF = (
    "examples/read_only_worker_active_runtime_lease_admission_witness.foundation.json"
)
EXPECTED_OPERATION_FAMILY = "local_repo_inspection"
EXPECTED_WITNESS_MODE = "UAO_DISPATCH_AUTHORIZATION_WITNESS_ONLY"
EXPECTED_TARGET_UAO_DISPATCH_AUTHORIZATION_REF = (
    "candidate://uao/dispatch-authorization/read-only-repo-inspection"
)
EXPECTED_UAO_AUTHORIZATION_PROFILE = "LOCAL_READ_ONLY_REPO_INSPECTION_UAO_DISPATCH_AUTHORIZATION"
EXPECTED_ADMISSION_DECISION = (
    "UAO_DISPATCH_AUTHORIZATION_WITNESS_BLOCKED_AWAITING_AUTHORIZATION_EVIDENCE"
)

REQUIRED_SOURCE_RECEIPT_REFS = (
    EXPECTED_RUNTIME_DISPATCH_ADMISSION_WITNESS_REF,
    EXPECTED_ACTIVE_RUNTIME_LEASE_ADMISSION_WITNESS_REF,
)
REQUIRED_AUTHORIZATION_INPUT_REFS = (
    "evidence://uao/action-orchestration/request",
    "evidence://uao/action-classification/effect-bearing",
    "evidence://uao/no-bypass/dispatch",
    "evidence://uao/policy-decision/allow",
    "evidence://uao/tenant-actor-worker-scope-bound",
    "evidence://uao/capability-boundary/read-only-repo-inspection",
    "evidence://uao/active-runtime-lease-admission",
    "evidence://uao/runtime-dispatch-admission-boundary",
    "evidence://uao/rollback-recovery-plan",
    "evidence://uao/worker-failure-receipt-on-error",
    "evidence://uao/effect-reconciliation-required",
    "evidence://phi-gov/dispatch-authorization",
    "evidence://runtime-clock/trusted-now",
)
REQUIRED_VALIDATION_REFS = (
    "scripts/validate_read_only_worker_uao_dispatch_authorization_witness.py",
    "scripts/validate_read_only_worker_runtime_dispatch_admission_witness.py",
    "scripts/validate_read_only_worker_active_runtime_lease_admission_witness.py",
    "scripts/validate_schemas.py",
    "scripts/validate_protocol_manifest.py",
    "scripts/validate_sdlc_artifact.py",
    "tests/test_validate_read_only_worker_uao_dispatch_authorization_witness.py",
)
REQUIRED_REMAINING_DENIED_UNTIL_REFS = (
    "evidence://uao/action-orchestration/request",
    "evidence://uao/action-classification/effect-bearing",
    "evidence://uao/no-bypass/dispatch",
    "evidence://uao/policy-decision/allow",
    "evidence://uao/tenant-actor-worker-scope-bound",
    "evidence://uao/active-runtime-lease-admission",
    "evidence://uao/runtime-dispatch-admission-boundary",
    "evidence://phi-gov/dispatch-authorization",
    "evidence://runtime-clock/trusted-now",
    "evidence://uao/effect-reconciliation-required",
)
REQUIRED_BLOCKED_REASON_REFS = (
    "blocked://uao/request-missing",
    "blocked://uao/effect-classification-missing",
    "blocked://uao/no-bypass-not-proven",
    "blocked://uao/policy-decision-missing",
    "blocked://uao/scope-binding-missing",
    "blocked://uao/active-lease-admission-missing",
    "blocked://uao/runtime-dispatch-admission-boundary-missing",
    "blocked://phi-gov/dispatch-not-authorized",
    "blocked://runtime-clock/trusted-now-missing",
    "blocked://effect-reconciliation/not-proven",
)
REQUIRED_RECEIPT_REFS = {
    "read_only_worker_uao_dispatch_authorization_witness_schema": (
        "schemas/read_only_worker_uao_dispatch_authorization_witness.schema.json"
    ),
    "read_only_worker_runtime_dispatch_admission_witness_schema": (
        "schemas/read_only_worker_runtime_dispatch_admission_witness.schema.json"
    ),
    "read_only_worker_active_runtime_lease_admission_witness_schema": (
        "schemas/read_only_worker_active_runtime_lease_admission_witness.schema.json"
    ),
    "worker_failure_receipt_schema": "schemas/worker_failure_receipt.schema.json",
    "universal_action_orchestration_schema": "schemas/universal_action_orchestration.schema.json",
}
REQUIRED_EVIDENCE_REFS = (
    "schemas/read_only_worker_uao_dispatch_authorization_witness.schema.json",
    "examples/read_only_worker_uao_dispatch_authorization_witness.foundation.json",
    "scripts/validate_read_only_worker_uao_dispatch_authorization_witness.py",
    "tests/test_validate_read_only_worker_uao_dispatch_authorization_witness.py",
    "schemas/read_only_worker_runtime_dispatch_admission_witness.schema.json",
    "examples/read_only_worker_runtime_dispatch_admission_witness.foundation.json",
    "scripts/validate_read_only_worker_runtime_dispatch_admission_witness.py",
    "tests/test_validate_read_only_worker_runtime_dispatch_admission_witness.py",
    "schemas/read_only_worker_active_runtime_lease_admission_witness.schema.json",
    "examples/read_only_worker_active_runtime_lease_admission_witness.foundation.json",
    "scripts/validate_read_only_worker_active_runtime_lease_admission_witness.py",
    "tests/test_validate_read_only_worker_active_runtime_lease_admission_witness.py",
    "schemas/worker_failure_receipt.schema.json",
    "schemas/universal_action_orchestration.schema.json",
    "docs/80_read_only_worker_binding_contract.md",
)
TRUE_ACTIVATION_FIELDS = (
    "upstream_runtime_dispatch_admission_witness_validated",
    "upstream_active_runtime_lease_admission_witness_validated",
    "uao_request_required",
    "effect_bearing_classification_required",
    "no_bypass_rule_required",
    "policy_allow_decision_required",
    "tenant_actor_worker_scope_required",
    "active_runtime_lease_admission_required",
    "runtime_clock_required",
    "phi_gov_authorization_required_before_dispatch",
    "worker_failure_receipt_required_on_error",
    "effect_reconciliation_required",
    "mfidel_atomicity_preserved",
)
DENIED_AUTHORITY_FIELDS = (
    "active_runtime_lease_observed",
    "uao_dispatch_authorization_performed",
    "phi_gov_dispatch_authorization_performed",
    "runtime_dispatch_admission_performed",
    "dispatch_admission_allowed",
    "runtime_dispatch_allowed",
    "worker_invocation_allowed",
    "runtime_receipt_emission_allowed",
    "receipt_append_allowed",
    "external_network_allowed",
    "secret_access_allowed",
    "filesystem_write_allowed",
    "connector_authority_allowed",
    "terminal_closure_allowed",
    "success_claim_allowed",
)
DENIED_ACTIVATION_FIELDS = (
    "active_runtime_lease_observed",
    "uao_dispatch_authorization_performed",
    "phi_gov_dispatch_authorization_performed",
    "runtime_dispatch_admission_performed",
    "dispatch_admission_allowed",
    "runtime_dispatch_allowed",
    "worker_invocation_allowed",
    "runtime_receipt_emitted",
    "receipt_append_performed",
)


class ReadOnlyWorkerUaoDispatchAuthorizationWitnessError(ValueError):
    """Raised when a witness artifact cannot be loaded."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {json_path}")
    if not json_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ReadOnlyWorkerUaoDispatchAuthorizationWitnessError(
            f"{label} must be a JSON object"
        )
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
            "runtime_dispatch_admission_witness_ref",
            "active_runtime_lease_admission_witness_ref",
            "authority_scope",
            "uao_dispatch_authorization_contract",
            "activation_evaluation",
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


def _require_refs(
    observed: Any,
    required: tuple[str, ...],
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(observed, list):
        errors.append(f"{label} must be a list")
        return
    observed_set = set(observed)
    for required_ref in required:
        if required_ref not in observed_set:
            errors.append(f"{label} missing required ref: {required_ref}")


def _count_true_values(mapping: Any, field_names: tuple[str, ...]) -> int:
    if not isinstance(mapping, dict):
        return 0
    return sum(1 for field_name in field_names if mapping.get(field_name) is True)


def _count_false_values(mapping: Any, field_names: tuple[str, ...]) -> int:
    if not isinstance(mapping, dict):
        return 0
    return sum(1 for field_name in field_names if mapping.get(field_name) is False)


def validate_uao_dispatch_authorization_witness_record(
    record: Any,
    schema: dict[str, Any] | None = None,
    runtime_dispatch_admission_witness: dict[str, Any] | None = None,
    active_runtime_lease_admission_witness: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one witness payload."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = validate_schema_artifact(schema_payload)

    if not isinstance(record, dict):
        errors.append("ReadOnlyWorkerUaoDispatchAuthorizationWitness must be object")
        return errors

    errors.extend(_validate_schema_instance(schema_payload, record))

    dispatch_witness_payload = runtime_dispatch_admission_witness
    if dispatch_witness_payload is None:
        dispatch_witness_payload = load_runtime_dispatch_admission_json_object(
            DEFAULT_RUNTIME_DISPATCH_ADMISSION_WITNESS_PATH,
            "ReadOnlyWorkerRuntimeDispatchAdmissionWitness",
        )
    dispatch_witness_schema = _load_schema(DEFAULT_RUNTIME_DISPATCH_ADMISSION_WITNESS_SCHEMA_PATH)
    errors.extend(
        f"runtime_dispatch_admission_witness: {error}"
        for error in validate_runtime_dispatch_admission_witness_record(
            dispatch_witness_payload,
            dispatch_witness_schema,
        )
    )

    active_lease_payload = active_runtime_lease_admission_witness
    if active_lease_payload is None:
        active_lease_payload = load_active_runtime_lease_admission_json_object(
            DEFAULT_ACTIVE_RUNTIME_LEASE_ADMISSION_WITNESS_PATH,
            "ReadOnlyWorkerActiveRuntimeLeaseAdmissionWitness",
        )
    active_lease_schema = _load_schema(DEFAULT_ACTIVE_RUNTIME_LEASE_ADMISSION_WITNESS_SCHEMA_PATH)
    errors.extend(
        f"active_runtime_lease_admission_witness: {error}"
        for error in validate_active_runtime_lease_admission_witness_record(
            active_lease_payload,
            active_lease_schema,
        )
    )

    if record.get("receipt_version") != EXPECTED_RECEIPT_VERSION:
        errors.append(
            "receipt_version must match read_only_worker_uao_dispatch_authorization_witness.v1"
        )
    if record.get("runtime_dispatch_admission_witness_ref") != EXPECTED_RUNTIME_DISPATCH_ADMISSION_WITNESS_REF:
        errors.append("runtime_dispatch_admission_witness_ref is invalid")
    if record.get("active_runtime_lease_admission_witness_ref") != (
        EXPECTED_ACTIVE_RUNTIME_LEASE_ADMISSION_WITNESS_REF
    ):
        errors.append("active_runtime_lease_admission_witness_ref is invalid")
    if record.get("selected_worker_path") != EXPECTED_WORKER_PATH:
        errors.append("selected_worker_path must be read_only_repo_inspection")

    authority = record.get("authority_scope")
    if not isinstance(authority, dict):
        errors.append("authority_scope must be an object")
    else:
        if authority.get("read_only") is not True:
            errors.append("authority_scope.read_only must be true")
        if authority.get("foundation_witness_only") is not True:
            errors.append("authority_scope.foundation_witness_only must be true")
        if authority.get("uao_dispatch_authorization_witness_defined") is not True:
            errors.append(
                "authority_scope.uao_dispatch_authorization_witness_defined must be true"
            )
        if authority.get("mfidel_atomicity_preserved") is not True:
            errors.append("authority_scope.mfidel_atomicity_preserved must be true")
        for field_name in DENIED_AUTHORITY_FIELDS:
            if authority.get(field_name) is not False:
                errors.append(f"authority_scope.{field_name} must be false")

    contract = record.get("uao_dispatch_authorization_contract")
    if not isinstance(contract, dict):
        errors.append("uao_dispatch_authorization_contract must be an object")
    else:
        if contract.get("worker_id") != EXPECTED_WORKER_ID:
            errors.append("uao_dispatch_authorization_contract.worker_id is invalid")
        if contract.get("capability") != EXPECTED_WORKER_PATH:
            errors.append("uao_dispatch_authorization_contract.capability is invalid")
        if contract.get("operation_family") != EXPECTED_OPERATION_FAMILY:
            errors.append("uao_dispatch_authorization_contract.operation_family is invalid")
        if contract.get("witness_mode") != EXPECTED_WITNESS_MODE:
            errors.append(
                "uao_dispatch_authorization_contract.witness_mode must be "
                "UAO_DISPATCH_AUTHORIZATION_WITNESS_ONLY"
            )
        if contract.get("source_runtime_dispatch_admission_witness_ref") != (
            EXPECTED_RUNTIME_DISPATCH_ADMISSION_WITNESS_REF
        ):
            errors.append(
                "uao_dispatch_authorization_contract."
                "source_runtime_dispatch_admission_witness_ref is invalid"
            )
        if contract.get("source_active_runtime_lease_admission_witness_ref") != (
            EXPECTED_ACTIVE_RUNTIME_LEASE_ADMISSION_WITNESS_REF
        ):
            errors.append(
                "uao_dispatch_authorization_contract."
                "source_active_runtime_lease_admission_witness_ref is invalid"
            )
        if contract.get("target_uao_dispatch_authorization_ref") != (
            EXPECTED_TARGET_UAO_DISPATCH_AUTHORIZATION_REF
        ):
            errors.append(
                "uao_dispatch_authorization_contract."
                "target_uao_dispatch_authorization_ref is invalid"
            )
        if contract.get("uao_authorization_profile") != EXPECTED_UAO_AUTHORIZATION_PROFILE:
            errors.append("uao_dispatch_authorization_contract.uao_authorization_profile is invalid")
        _require_refs(
            contract.get("required_source_receipt_refs"),
            REQUIRED_SOURCE_RECEIPT_REFS,
            "uao_dispatch_authorization_contract.required_source_receipt_refs",
            errors,
        )
        _require_refs(
            contract.get("required_authorization_input_refs"),
            REQUIRED_AUTHORIZATION_INPUT_REFS,
            "uao_dispatch_authorization_contract.required_authorization_input_refs",
            errors,
        )
        _require_refs(
            contract.get("validation_refs"),
            REQUIRED_VALIDATION_REFS,
            "uao_dispatch_authorization_contract.validation_refs",
            errors,
        )

    activation = record.get("activation_evaluation")
    if not isinstance(activation, dict):
        errors.append("activation_evaluation must be an object")
    else:
        for field_name in TRUE_ACTIVATION_FIELDS:
            if activation.get(field_name) is not True:
                errors.append(f"activation_evaluation.{field_name} must be true")
        for field_name in DENIED_ACTIVATION_FIELDS:
            if activation.get(field_name) is not False:
                errors.append(f"activation_evaluation.{field_name} must be false")

    decision = record.get("admission_decision")
    if not isinstance(decision, dict):
        errors.append("admission_decision must be an object")
    else:
        if decision.get("decision") != EXPECTED_ADMISSION_DECISION:
            errors.append("admission_decision.decision is invalid")
        if decision.get("uao_dispatch_authorized") is not False:
            errors.append("admission_decision.uao_dispatch_authorized must be false")
        if decision.get("phi_gov_dispatch_authorized") is not False:
            errors.append("admission_decision.phi_gov_dispatch_authorized must be false")
        if decision.get("runtime_dispatch_admitted") is not False:
            errors.append("admission_decision.runtime_dispatch_admitted must be false")
        if decision.get("terminal_closure_allowed") is not False:
            errors.append("admission_decision.terminal_closure_allowed must be false")
        if decision.get("uao_dispatch_authorization_witness_defined") is not True:
            errors.append(
                "admission_decision.uao_dispatch_authorization_witness_defined must be true"
            )
        _require_refs(
            decision.get("remaining_denied_until_refs"),
            REQUIRED_REMAINING_DENIED_UNTIL_REFS,
            "admission_decision.remaining_denied_until_refs",
            errors,
        )
        _require_refs(
            decision.get("blocked_reason_refs"),
            REQUIRED_BLOCKED_REASON_REFS,
            "admission_decision.blocked_reason_refs",
            errors,
        )

    receipt_refs = record.get("receipt_refs")
    if not isinstance(receipt_refs, dict):
        errors.append("receipt_refs must be an object")
    else:
        for key, expected_value in REQUIRED_RECEIPT_REFS.items():
            if receipt_refs.get(key) != expected_value:
                errors.append(f"receipt_refs.{key} is invalid")

    evidence_refs = record.get("evidence_refs")
    _require_refs(evidence_refs, REQUIRED_EVIDENCE_REFS, "evidence_refs", errors)

    summary = record.get("contract_summary")
    if not isinstance(summary, dict):
        errors.append("contract_summary must be an object")
    else:
        source_refs = contract.get("required_source_receipt_refs") if isinstance(contract, dict) else []
        authorization_refs = (
            contract.get("required_authorization_input_refs")
            if isinstance(contract, dict)
            else []
        )
        obligations = contract.get("activation_obligations_checked") if isinstance(contract, dict) else []
        validation_refs = contract.get("validation_refs") if isinstance(contract, dict) else []
        remaining_refs = decision.get("remaining_denied_until_refs") if isinstance(decision, dict) else []
        blocked_refs = decision.get("blocked_reason_refs") if isinstance(decision, dict) else []
        summary_expectations = {
            "source_receipt_ref_count": len(source_refs) if isinstance(source_refs, list) else 0,
            "authorization_input_ref_count": (
                len(authorization_refs) if isinstance(authorization_refs, list) else 0
            ),
            "activation_obligation_count": len(obligations) if isinstance(obligations, list) else 0,
            "validation_ref_count": len(validation_refs) if isinstance(validation_refs, list) else 0,
            "activation_true_check_count": _count_true_values(activation, TRUE_ACTIVATION_FIELDS),
            "activation_denied_check_count": _count_false_values(activation, DENIED_ACTIVATION_FIELDS),
            "remaining_denied_until_ref_count": len(remaining_refs) if isinstance(remaining_refs, list) else 0,
            "blocked_reason_ref_count": len(blocked_refs) if isinstance(blocked_refs, list) else 0,
            "receipt_ref_count": len(receipt_refs) if isinstance(receipt_refs, dict) else 0,
            "evidence_ref_count": len(evidence_refs) if isinstance(evidence_refs, list) else 0,
        }
        for field_name, expected_count in summary_expectations.items():
            if summary.get(field_name) != expected_count:
                errors.append(f"contract_summary.{field_name} must match observed count")

    return errors


def validate_uao_dispatch_authorization_witness(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
) -> list[str]:
    """Validate schema, receipt, and upstream witness artifacts."""

    schema = _load_schema(schema_path)
    receipt = load_json_object(receipt_path, "ReadOnlyWorkerUaoDispatchAuthorizationWitness")
    return validate_uao_dispatch_authorization_witness_record(receipt, schema)


def build_mutated_uao_dispatch_authorization_witness(**updates: Any) -> dict[str, Any]:
    """Return a deep-copied fixture with double-underscore path updates."""

    receipt = load_json_object(
        DEFAULT_RECEIPT_PATH,
        "ReadOnlyWorkerUaoDispatchAuthorizationWitness",
    )
    mutated = deepcopy(receipt)
    for dotted_path, value in updates.items():
        keys = dotted_path.split("__")
        current: Any = mutated
        for key in keys[:-1]:
            current = current[key]
        current[keys[-1]] = value
    return mutated


def _workspace_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(WORKSPACE_ROOT))
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    """Validate ReadOnlyWorkerUaoDispatchAuthorizationWitness artifacts."""

    parser = argparse.ArgumentParser(
        description="Validate ReadOnlyWorkerUaoDispatchAuthorizationWitness contract."
    )
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    errors = validate_uao_dispatch_authorization_witness(args.schema, args.receipt)
    if args.json:
        payload = {
            "status": "passed" if not errors else "failed",
            "schema_path": _workspace_relative(args.schema),
            "receipt_path": _workspace_relative(args.receipt),
            "errors": errors,
            "receipt": {
                "receipt_id": "read_only_worker_uao_dispatch_authorization_witness_validation",
                "validated_artifact": _workspace_relative(args.receipt),
                "schema": _workspace_relative(args.schema),
                "error_count": len(errors),
            },
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif errors:
        print("[FAIL] read_only_worker_uao_dispatch_authorization_witness", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
    else:
        print("[PASS] read_only_worker_uao_dispatch_authorization_witness")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

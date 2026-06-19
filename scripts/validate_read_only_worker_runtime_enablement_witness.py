#!/usr/bin/env python3
"""Validate the ReadOnlyWorkerRuntimeEnablementWitness contract.

Purpose: verify Foundation Mode witness evidence for future runtime enablement
before read_only_repo_inspection runtime dispatch without appending a receipt,
authorizing UAO, authorizing Phi_gov, or admitting dispatch.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, schema validation helpers, and
ReadOnlyWorkerTerminalClosureWitness validation.
Invariants:
  - Validation is read-only and deterministic.
  - The witness applies only to read_only_repo_inspection.
  - UAO dispatch authorization, runtime enablement, runtime dispatch
    admission, runtime dispatch, worker invocation, receipt emission, receipt
    append, success claims, and runtime enablement remain unperformed.
  - Future runtime enablement still requires receipt append, final judgment,
    no-unexpected-effect proof, WorkerFailureReceipt obligations, and trusted
    runtime clock evidence.
  - Mfidel atomicity remains preserved.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from functools import lru_cache
import json
import sys
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_read_only_worker_binding import EXPECTED_WORKER_PATH  # noqa: E402
from scripts.validate_read_only_worker_rehearsal_receipt import EXPECTED_WORKER_ID  # noqa: E402
from scripts.validate_read_only_worker_terminal_closure_witness import (  # noqa: E402
    DEFAULT_RECEIPT_PATH as DEFAULT_TERMINAL_CLOSURE_WITNESS_PATH,
    DEFAULT_SCHEMA_PATH as DEFAULT_TERMINAL_CLOSURE_WITNESS_SCHEMA_PATH,
    load_json_object as load_terminal_closure_json_object,
    validate_terminal_closure_witness_record,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = (
    WORKSPACE_ROOT
    / "schemas"
    / "read_only_worker_runtime_enablement_witness.schema.json"
)
DEFAULT_RECEIPT_PATH = (
    WORKSPACE_ROOT
    / "examples"
    / "read_only_worker_runtime_enablement_witness.foundation.json"
)
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:read-only-worker-runtime-enablement-witness:1"
EXPECTED_SCHEMA_TITLE = "Read-Only Worker Runtime Enablement Witness"
EXPECTED_RECEIPT_VERSION = "read_only_worker_runtime_enablement_witness.v1"
EXPECTED_TERMINAL_CLOSURE_WITNESS_REF = (
    "examples/read_only_worker_terminal_closure_witness.foundation.json"
)
EXPECTED_OPERATION_FAMILY = "local_repo_inspection"
EXPECTED_WITNESS_MODE = "RUNTIME_ENABLEMENT_WITNESS_ONLY"
EXPECTED_TARGET_RUNTIME_ENABLEMENT_REF = (
    "candidate://runtime-enablement/read-only-repo-inspection"
)
EXPECTED_CLOSURE_PROFILE = (
    "LOCAL_READ_ONLY_REPO_INSPECTION_RUNTIME_ENABLEMENT"
)
EXPECTED_ADMISSION_DECISION = (
    "RUNTIME_ENABLEMENT_WITNESS_BLOCKED_AWAITING_ENABLEMENT_EVIDENCE"
)

REQUIRED_SOURCE_RECEIPT_REFS = (
    EXPECTED_TERMINAL_CLOSURE_WITNESS_REF,
)
REQUIRED_AUTHORIZATION_INPUT_REFS = (
    "evidence://terminal-closure/certificate",
    "evidence://runtime-runner/registered",
    "evidence://runtime-dispatch-endpoint/registered",
    "evidence://runtime-receipt-emitter/registered",
    "evidence://runtime-receipt-store/activated",
    "evidence://operator-approval/runtime-enablement",
    "evidence://active-runtime-lease/observed",
    "evidence://uao-dispatch-authorization",
    "evidence://phi-gov-dispatch-authorization",
    "evidence://runtime-dispatch-admission",
    "evidence://runtime-disablement-rollback-plan",
    "evidence://worker-failure-receipt-on-error",
    "evidence://runtime-clock/trusted-now",
)
REQUIRED_VALIDATION_REFS = (
    "scripts/validate_read_only_worker_runtime_enablement_witness.py",
    "scripts/validate_read_only_worker_terminal_closure_witness.py",
    "scripts/validate_schemas.py",
    "scripts/validate_protocol_manifest.py",
    "scripts/validate_sdlc_artifact.py",
    "tests/test_validate_read_only_worker_runtime_enablement_witness.py",
)
REQUIRED_REMAINING_DENIED_UNTIL_REFS = (
    "evidence://terminal-closure/certificate",
    "evidence://runtime-runner/registered",
    "evidence://runtime-dispatch-endpoint/registered",
    "evidence://runtime-receipt-emitter/registered",
    "evidence://runtime-receipt-store/activated",
    "evidence://operator-approval/runtime-enablement",
    "evidence://active-runtime-lease/observed",
    "evidence://uao-dispatch-authorization",
    "evidence://phi-gov-dispatch-authorization",
    "evidence://runtime-dispatch-admission",
    "evidence://runtime-disablement-rollback-plan",
    "evidence://runtime-clock/trusted-now",
)
REQUIRED_BLOCKED_REASON_REFS = (
    "blocked://terminal-closure/certificate-missing",
    "blocked://runtime-runner/not-registered",
    "blocked://runtime-dispatch-endpoint/not-registered",
    "blocked://runtime-receipt-emitter/not-registered",
    "blocked://runtime-receipt-store/not-activated",
    "blocked://operator-approval/runtime-enablement-missing",
    "blocked://active-runtime-lease/not-observed",
    "blocked://uao-dispatch-authorization/missing",
    "blocked://phi-gov-dispatch-authorization/missing",
    "blocked://runtime-dispatch-admission/missing",
    "blocked://runtime-disablement-rollback-plan/missing",
    "blocked://runtime-clock/trusted-now-missing",
)
REQUIRED_RECEIPT_REFS = {
    "read_only_worker_runtime_enablement_witness_schema": (
        "schemas/read_only_worker_runtime_enablement_witness.schema.json"
    ),
    "read_only_worker_terminal_closure_witness_schema": (
        "schemas/read_only_worker_terminal_closure_witness.schema.json"
    ),
    "runtime_conformance_certificate_schema": (
        "schemas/runtime_conformance_certificate.schema.json"
    ),
    "worker_failure_receipt_schema": "schemas/worker_failure_receipt.schema.json",
    "universal_action_orchestration_schema": "schemas/universal_action_orchestration.schema.json",
}
REQUIRED_EVIDENCE_REFS = (
    "schemas/read_only_worker_runtime_enablement_witness.schema.json",
    "examples/read_only_worker_runtime_enablement_witness.foundation.json",
    "scripts/validate_read_only_worker_runtime_enablement_witness.py",
    "tests/test_validate_read_only_worker_runtime_enablement_witness.py",
    "schemas/read_only_worker_terminal_closure_witness.schema.json",
    "examples/read_only_worker_terminal_closure_witness.foundation.json",
    "scripts/validate_read_only_worker_terminal_closure_witness.py",
    "tests/test_validate_read_only_worker_terminal_closure_witness.py",
    "schemas/runtime_conformance_certificate.schema.json",
    "schemas/worker_failure_receipt.schema.json",
    "schemas/universal_action_orchestration.schema.json",
    "docs/80_read_only_worker_binding_contract.md",
)
TRUE_ACTIVATION_FIELDS = (
    "upstream_terminal_closure_witness_validated",
    "runtime_runner_registration_required",
    "dispatch_endpoint_registration_required",
    "receipt_emitter_registration_required",
    "receipt_store_activation_required",
    "operator_runtime_enablement_approval_required",
    "active_runtime_lease_required",
    "uao_dispatch_authorization_required",
    "phi_gov_dispatch_authorization_required",
    "runtime_dispatch_admission_required",
    "rollback_plan_required",
    "runtime_clock_required",
    "worker_failure_receipt_required_on_error",
    "mfidel_atomicity_preserved",
)
DENIED_AUTHORITY_FIELDS = (
    "active_runtime_lease_observed",
    "uao_dispatch_authorization_performed",
    "runtime_enablement_performed",
    "runtime_dispatch_admission_performed",
    "dispatch_admission_allowed",
    "runtime_dispatch_allowed",
    "worker_invocation_allowed",
    "runtime_receipt_emission_allowed",
    "runtime_enablement_allowed",
    "external_network_allowed",
    "secret_access_allowed",
    "filesystem_write_allowed",
    "connector_authority_allowed",
    "success_claim_allowed",
)
DENIED_ACTIVATION_FIELDS = (
    "active_runtime_lease_observed",
    "uao_dispatch_authorization_performed",
    "runtime_enablement_performed",
    "runtime_dispatch_admission_performed",
    "dispatch_admission_allowed",
    "runtime_dispatch_allowed",
    "worker_invocation_allowed",
    "runtime_receipt_emitted",
)


class ReadOnlyWorkerRuntimeEnablementWitnessError(ValueError):
    """Raised when a witness artifact cannot be loaded."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {json_path}")
    if not json_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ReadOnlyWorkerRuntimeEnablementWitnessError(
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
            "terminal_closure_witness_ref",
            "authority_scope",
            "runtime_enablement_contract",
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


@lru_cache(maxsize=1)
def _validate_default_upstream_witnesses() -> tuple[str, ...]:
    """Return cached errors for default upstream witness artifacts."""

    upstream_errors: list[str] = []
    terminal_closure_payload = load_terminal_closure_json_object(
        DEFAULT_TERMINAL_CLOSURE_WITNESS_PATH,
        "ReadOnlyWorkerTerminalClosureWitness",
    )
    terminal_closure_schema = _load_schema(
        DEFAULT_TERMINAL_CLOSURE_WITNESS_SCHEMA_PATH
    )
    upstream_errors.extend(
        f"terminal_closure_witness: {error}"
        for error in validate_terminal_closure_witness_record(
            terminal_closure_payload,
            terminal_closure_schema,
        )
    )
    return tuple(upstream_errors)

def validate_runtime_enablement_witness_record(
    record: Any,
    schema: dict[str, Any] | None = None,
    terminal_closure_witness: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one witness payload."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = validate_schema_artifact(schema_payload)

    if not isinstance(record, dict):
        errors.append("ReadOnlyWorkerRuntimeEnablementWitness must be object")
        return errors

    errors.extend(_validate_schema_instance(schema_payload, record))

    if terminal_closure_witness is None:
        errors.extend(_validate_default_upstream_witnesses())
    else:
        terminal_closure_schema = _load_schema(DEFAULT_TERMINAL_CLOSURE_WITNESS_SCHEMA_PATH)
        errors.extend(
            f"terminal_closure_witness: {error}"
            for error in validate_terminal_closure_witness_record(
                terminal_closure_witness,
                terminal_closure_schema,
            )
        )

    if record.get("receipt_version") != EXPECTED_RECEIPT_VERSION:
        errors.append(
            "receipt_version must match read_only_worker_runtime_enablement_witness.v1"
        )
    if record.get("terminal_closure_witness_ref") != (
        EXPECTED_TERMINAL_CLOSURE_WITNESS_REF
    ):
        errors.append("terminal_closure_witness_ref is invalid")
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
        if authority.get("runtime_enablement_witness_defined") is not True:
            errors.append(
                "authority_scope.runtime_enablement_witness_defined must be true"
            )
        if authority.get("mfidel_atomicity_preserved") is not True:
            errors.append("authority_scope.mfidel_atomicity_preserved must be true")
        for field_name in DENIED_AUTHORITY_FIELDS:
            if authority.get(field_name) is not False:
                errors.append(f"authority_scope.{field_name} must be false")

    contract = record.get("runtime_enablement_contract")
    if not isinstance(contract, dict):
        errors.append("runtime_enablement_contract must be an object")
    else:
        if contract.get("worker_id") != EXPECTED_WORKER_ID:
            errors.append("runtime_enablement_contract.worker_id is invalid")
        if contract.get("capability") != EXPECTED_WORKER_PATH:
            errors.append("runtime_enablement_contract.capability is invalid")
        if contract.get("operation_family") != EXPECTED_OPERATION_FAMILY:
            errors.append("runtime_enablement_contract.operation_family is invalid")
        if contract.get("witness_mode") != EXPECTED_WITNESS_MODE:
            errors.append(
                "runtime_enablement_contract.witness_mode must be "
                "RUNTIME_ENABLEMENT_WITNESS_ONLY"
            )
        if contract.get("source_terminal_closure_witness_ref") != (
            EXPECTED_TERMINAL_CLOSURE_WITNESS_REF
        ):
            errors.append(
                "runtime_enablement_contract."
                "source_terminal_closure_witness_ref is invalid"
            )
        if contract.get("target_runtime_enablement_ref") != (
            EXPECTED_TARGET_RUNTIME_ENABLEMENT_REF
        ):
            errors.append(
                "runtime_enablement_contract."
                "target_runtime_enablement_ref is invalid"
            )
        if contract.get("closure_profile") != EXPECTED_CLOSURE_PROFILE:
            errors.append(
                "runtime_enablement_contract.closure_profile is invalid"
            )
        _require_refs(
            contract.get("required_source_receipt_refs"),
            REQUIRED_SOURCE_RECEIPT_REFS,
            "runtime_enablement_contract.required_source_receipt_refs",
            errors,
        )
        _require_refs(
            contract.get("required_authorization_input_refs"),
            REQUIRED_AUTHORIZATION_INPUT_REFS,
            "runtime_enablement_contract.required_authorization_input_refs",
            errors,
        )
        _require_refs(
            contract.get("validation_refs"),
            REQUIRED_VALIDATION_REFS,
            "runtime_enablement_contract.validation_refs",
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
        if decision.get("runtime_enablement_allowed") is not False:
            errors.append("admission_decision.runtime_enablement_allowed must be false")
        if decision.get("runtime_enablement_witness_defined") is not True:
            errors.append(
                "admission_decision.runtime_enablement_witness_defined must be true"
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


def validate_runtime_enablement_witness(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
) -> list[str]:
    """Validate schema, receipt, and upstream witness artifacts."""

    schema = _load_schema(schema_path)
    receipt = load_json_object(receipt_path, "ReadOnlyWorkerRuntimeEnablementWitness")
    return validate_runtime_enablement_witness_record(receipt, schema)


def build_mutated_runtime_enablement_witness(**updates: Any) -> dict[str, Any]:
    """Return a deep-copied fixture with double-underscore path updates."""

    receipt = load_json_object(
        DEFAULT_RECEIPT_PATH,
        "ReadOnlyWorkerRuntimeEnablementWitness",
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
    """Validate ReadOnlyWorkerRuntimeEnablementWitness artifacts."""

    parser = argparse.ArgumentParser(
        description="Validate ReadOnlyWorkerRuntimeEnablementWitness contract."
    )
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    errors = validate_runtime_enablement_witness(args.schema, args.receipt)
    if args.json:
        payload = {
            "status": "passed" if not errors else "failed",
            "schema_path": _workspace_relative(args.schema),
            "receipt_path": _workspace_relative(args.receipt),
            "errors": errors,
            "receipt": {
                "receipt_id": "read_only_worker_runtime_enablement_witness_validation",
                "validated_artifact": _workspace_relative(args.receipt),
                "schema": _workspace_relative(args.schema),
                "error_count": len(errors),
            },
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif errors:
        print("[FAIL] read_only_worker_runtime_enablement_witness", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
    else:
        print("[PASS] read_only_worker_runtime_enablement_witness")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

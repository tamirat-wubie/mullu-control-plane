#!/usr/bin/env python3
"""Validate operator value-binding verifier execution decision-value record path."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for candidate in (REPO_ROOT, MCOI_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from mcoi_runtime.personal_assistant import (  # noqa: E402
    DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_PATH_GENERATED_AT,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_path,
)
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_path.schema.json"
)
DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"
RUNTIME_GENERATED_AT = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_PATH_GENERATED_AT
EXPECTED_RECORD_KINDS = (
    "explicit_operator_approval",
    "explicit_operator_rejection",
    "explicit_operator_revision_request",
    "explicit_operator_expiry",
)
EXPECTED_REJECTED_INPUT_KINDS = ("generic_continuation", "template_packet")
EXPECTED_REQUIRED_FIELDS = (
    "operator_decision_value_ref",
    "operator_identity_ref",
    "operator_signature_ref",
    "operator_reapproval_decision_receipt_ref",
)
EXPECTED_EVIDENCE_KINDS = frozenset(EXPECTED_REQUIRED_FIELDS)
EXPECTED_REQUIREMENT_KINDS = frozenset(
    {
        "verifier_identity_ref",
        "verification_method_ref",
        "evidence_integrity_hash_ref",
        "source_ref_reachability_witness_ref",
        "decision_receipt_crosscheck_ref",
    }
)
FALSE_FIELDS = frozenset(
    {
        "record_path_admitted",
        "collection_gate_satisfied",
        "operator_value_record_created",
        "operator_decision_value_stored",
        "operator_decision_value_present",
        "operator_decision_value_collected",
        "operator_decision_value_submitted",
        "operator_decision_value_admitted",
        "operator_decision_present",
        "operator_decision_intake_completed",
        "operator_approval_granted",
        "operator_approval_rejected",
        "operator_decision_value_accepted",
        "operator_decision_value_rejected",
        "ready_for_verifier_execution",
        "verifier_execution_allowed",
        "verifier_execution_started",
        "verifier_execution_completed",
        "verifier_result_present",
        "verifier_ref_validated",
        "evidence_verified",
        "evidence_accepted",
        "evidence_rejected",
        "binding_record_created",
        "binding_record_admitted",
        "authority_granted",
        "execution_worker_admission_allowed",
        "dispatch_allowed",
        "dispatch_lease_active",
        "live_connector_execution_allowed",
        "connector_mutation_allowed",
        "system_of_record_write_allowed",
        "memory_write_allowed",
        "deployment_mutation_allowed",
        "nested_mind_live_activation_allowed",
        "public_readiness_claim_allowed",
    }
)
FALSE_AUTHORITY_FIELDS = frozenset(
    {
        "operator_value_bound",
        "operator_value_record_created",
        "operator_value_record_admitted",
        "binding_record_created",
        "binding_record_admitted",
        "authority_granted",
        "execution_worker_admission_allowed",
        "dispatch_allowed",
        "dispatch_lease_active",
        "live_connector_receipt_present",
        "live_connector_execution_allowed",
        "connector_mutation_allowed",
        "system_of_record_write_allowed",
        "memory_write_allowed",
    }
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"sk_live_[A-Za-z0-9]+"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"ya29\.[A-Za-z0-9._-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"secret-(?:token|worker|key)-value", re.IGNORECASE),
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantOperatorReapprovalDecisionReceiptValueBindingRecordVerifierExecutionDecisionValueRecordPathValidation:
    """Validation result for verifier execution decision-value record path."""

    valid: bool
    runtime_validated: bool
    record_path_count: int
    record_contract_ready_count: int
    record_path_admission_count: int
    collection_gate_satisfied_count: int
    operator_value_record_creation_count: int
    operator_decision_value_storage_count: int
    operator_decision_value_present_count: int
    verifier_execution_allowed_count: int
    authority_grant_count: int
    assurance_outcome: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_path(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
) -> PersonalAssistantOperatorReapprovalDecisionReceiptValueBindingRecordVerifierExecutionDecisionValueRecordPathValidation:
    """Validate runtime verifier execution decision-value record path."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "decision-value record path schema", errors)
    receipt_schema = _load_json_object(receipt_schema_path, "receipt schema", errors)
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_path(
        generated_at=RUNTIME_GENERATED_AT,
    )
    summary = _mapping(envelope.get("summary"))
    assurance = _mapping(envelope.get("assurance"))
    if schema:
        errors.extend(_validate_schema_instance(schema, envelope))
    errors.extend(_validate_decision_value_record_path_semantics(envelope, receipt_schema))
    _scan_secret_values(envelope, errors, path="$runtime")
    return PersonalAssistantOperatorReapprovalDecisionReceiptValueBindingRecordVerifierExecutionDecisionValueRecordPathValidation(
        valid=not errors,
        runtime_validated=not errors,
        record_path_count=int(envelope.get("record_path_count", 0)),
        record_contract_ready_count=int(summary.get("record_contract_ready_count", 0)),
        record_path_admission_count=int(summary.get("record_path_admission_count", 0)),
        collection_gate_satisfied_count=int(summary.get("collection_gate_satisfied_count", 0)),
        operator_value_record_creation_count=int(summary.get("operator_value_record_creation_count", 0)),
        operator_decision_value_storage_count=int(summary.get("operator_decision_value_storage_count", 0)),
        operator_decision_value_present_count=int(summary.get("operator_decision_value_present_count", 0)),
        verifier_execution_allowed_count=int(summary.get("verifier_execution_allowed_count", 0)),
        authority_grant_count=int(summary.get("authority_grant_count", 0)),
        assurance_outcome=str(assurance.get("outcome", "")),
        errors=tuple(errors),
    )


def _validate_decision_value_record_path_semantics(envelope: Mapping[str, Any], receipt_schema: Mapping[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    expected_top = {
        "record_path_state": "operator_decision_value_record_path_ready_blocked_awaiting_explicit_operator_value",
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "source_projection": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_collection_gate",
    }
    for field_name, expected_value in expected_top.items():
        if envelope.get(field_name) != expected_value:
            errors.append(f"{field_name} must be {expected_value}")
    effect_boundary = _mapping(envelope.get("effect_boundary"))
    for field_name in (
        "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_path_allowed",
        "decision_value_collection_gate_ref_binding_allowed",
        "operator_decision_value_record_path_projection_allowed",
        "collection_gates_present",
        "operator_decision_required",
        "operator_decision_value_required",
        "actual_operator_decision_value_required",
        "record_contract_ready",
        "verifier_ref_only",
    ):
        if effect_boundary.get(field_name) is not True:
            errors.append(f"effect_boundary.{field_name} must be true")
    _require_false_fields(effect_boundary, FALSE_FIELDS, "effect_boundary", errors)

    records = envelope.get("record_paths")
    if not isinstance(records, list):
        errors.append("record_paths must be a list")
        return tuple(errors)
    if envelope.get("record_path_count") != len(records):
        errors.append("record_path_count must equal record_paths length")
    item_ids: list[str] = []
    receipt_ids: list[str] = []
    coverage: dict[str, set[str]] = {}
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"record_paths[{index}] must be an object")
            continue
        item_ids.append(str(record.get("record_path_item_id", "")))
        evidence_kind = str(record.get("evidence_kind", ""))
        requirement_kind = str(record.get("requirement_kind", ""))
        coverage.setdefault(evidence_kind, set()).add(requirement_kind)
        _require_source_ref(index, _mapping(record.get("collection_gate_ref")), errors)
        _require_record_path(index, _mapping(record.get("record_path")), errors)
        _require_false_fields(_mapping(record.get("authority_status")), FALSE_AUTHORITY_FIELDS, f"record_paths[{index}].authority_status", errors)
        receipt = _mapping(record.get("receipt"))
        if receipt_schema:
            errors.extend(f"record_paths[{index}].receipt {message}" for message in _validate_schema_instance(dict(receipt_schema), receipt))
        errors.extend(f"record_paths[{index}].receipt {message}" for message in validate_personal_assistant_receipt_payload(receipt))
        metadata = _mapping(receipt.get("metadata"))
        if metadata.get("operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_path_is_execution") is not False:
            errors.append(f"record_paths[{index}].receipt.metadata execution flag must be false")
        if metadata.get("record_path_created") is not True:
            errors.append(f"record_paths[{index}].receipt.metadata record_path_created must be true")
        _require_false_fields(metadata, FALSE_FIELDS | {"external_write_allowed"}, f"record_paths[{index}].receipt.metadata", errors)
        receipt_ids.append(str(receipt.get("receipt_id", "")))
    if set(coverage) != EXPECTED_EVIDENCE_KINDS:
        errors.append("record_paths must cover all governed evidence kinds")
    for evidence_kind, requirement_kinds in coverage.items():
        if requirement_kinds != EXPECTED_REQUIREMENT_KINDS:
            errors.append(f"record_paths for {evidence_kind} must cover all verifier requirement kinds")
    if envelope.get("record_path_item_ids") != item_ids:
        errors.append("record_path_item_ids must match item order")
    if envelope.get("receipt_ids") != receipt_ids:
        errors.append("receipt_ids must match item receipts")
    _require_summary(envelope, records, errors)
    return tuple(errors)


def _require_source_ref(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    expected = {
        "source_collection_gate_state": "operator_decision_value_collection_gate_blocked_awaiting_explicit_operator_value",
        "source_outcome": "AwaitingEvidence",
        "source_collection_gate_created": True,
        "source_operator_decision_required": True,
        "source_operator_decision_value_required": True,
        "source_actual_operator_decision_value_required": True,
        "source_collection_route_admitted": False,
        "source_template_accepted_as_value": False,
        "source_operator_decision_value_present": False,
        "source_operator_decision_value_collected": False,
        "source_operator_decision_value_submitted": False,
        "source_operator_decision_value_admitted": False,
        "source_operator_decision_present": False,
        "source_operator_approval_granted": False,
        "source_operator_approval_rejected": False,
        "source_verifier_execution_allowed": False,
        "source_verifier_execution_started": False,
        "source_authority_granted": False,
    }
    for field_name, expected_value in expected.items():
        if payload.get(field_name) != expected_value:
            errors.append(f"record_paths[{index}].collection_gate_ref.{field_name} must be {expected_value}")


def _require_record_path(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    for field_name in (
        "record_contract_ready",
        "record_path_created",
        "operator_decision_required",
        "operator_decision_value_required",
        "actual_operator_decision_value_required",
        "requires_collection_gate_satisfied",
        "requires_actual_operator_value",
    ):
        if payload.get(field_name) is not True:
            errors.append(f"record_paths[{index}].record_path.{field_name} must be true")
    if tuple(payload.get("accepted_record_kinds", ())) != EXPECTED_RECORD_KINDS:
        errors.append(f"record_paths[{index}].record_path.accepted_record_kinds must match canonical values")
    if tuple(payload.get("rejected_input_kinds", ())) != EXPECTED_REJECTED_INPUT_KINDS:
        errors.append(f"record_paths[{index}].record_path.rejected_input_kinds must reject generic continuations and templates")
    if tuple(payload.get("required_fields", ())) != EXPECTED_REQUIRED_FIELDS:
        errors.append(f"record_paths[{index}].record_path.required_fields must match required operator refs")
    _require_false_fields(payload, FALSE_FIELDS | {"accepts_generic_continuation", "accepts_template_packet"}, f"record_paths[{index}].record_path", errors)
    if payload.get("blocking_reason") != "actual_operator_decision_value_absent_collection_gate_unsatisfied":
        errors.append(f"record_paths[{index}].record_path blocking_reason must remain governed")


def _require_summary(envelope: Mapping[str, Any], records: list[Any], errors: list[str]) -> None:
    summary = _mapping(envelope.get("summary"))
    expected = {
        "record_path_count": len(records),
        "record_contract_ready_count": len(records),
        "operator_decision_required_count": len(records),
        "operator_decision_value_required_count": len(records),
        "actual_operator_decision_value_required_count": len(records),
        "record_path_creation_count": len(records),
        "record_path_admission_count": 0,
        "collection_gate_satisfied_count": 0,
        "operator_value_record_creation_count": 0,
        "operator_decision_value_storage_count": 0,
        "operator_decision_value_present_count": 0,
        "operator_decision_value_admitted_count": 0,
        "operator_approval_grant_count": 0,
        "operator_approval_rejection_count": 0,
        "verifier_execution_allowed_count": 0,
        "verifier_execution_started_count": 0,
        "verifier_result_count": 0,
        "validated_verifier_ref_count": 0,
        "accepted_evidence_count": 0,
        "authority_grant_count": 0,
        "binding_record_creation_count": 0,
    }
    for field_name, expected_value in expected.items():
        if summary.get(field_name) != expected_value:
            errors.append(f"summary.{field_name} must be {expected_value}")


def _require_false_fields(payload: Mapping[str, Any], fields: frozenset[str], label: str, errors: list[str]) -> None:
    for field_name in sorted(fields):
        if payload.get(field_name) is not False:
            errors.append(f"{label}.{field_name} must be false")


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        errors.append(f"{label} unreadable: {exc}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"{label} is invalid JSON: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} must be a JSON object")
        return {}
    return payload


def _scan_secret_values(payload: Any, errors: list[str], *, path: str) -> None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            normalized_key = str(key).lower()
            if normalized_key in {
                "raw_operator_decision",
                "operator_decision_value",
                "raw_operator_value_record",
                "operator_value_record",
                "raw_verifier_payload",
                "verifier_result",
                "token",
                "secret",
                "private_key",
            }:
                errors.append(f"{path}.{key}: raw private or secret field is forbidden")
            _scan_secret_values(value, errors, path=f"{path}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _scan_secret_values(value, errors, path=f"{path}[{index}]")
    elif isinstance(payload, str) and any(pattern.search(payload) for pattern in SECRET_VALUE_PATTERNS):
        errors.append(f"{path}: secret-like value must not be serialized")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--receipt-schema", type=Path, default=DEFAULT_RECEIPT_SCHEMA)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_path(
        schema_path=args.schema,
        receipt_schema_path=args.receipt_schema,
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print("PERSONAL ASSISTANT OPERATOR REAPPROVAL DECISION RECEIPT VALUE BINDING RECORD VERIFIER EXECUTION DECISION VALUE RECORD PATH VALID")
    else:
        for error in result.errors:
            print(f"[ERROR] {error}", file=sys.stderr)
    return 0 if result.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate operator value-binding verifier execution preflight."""

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
    DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_PREFLIGHT_GENERATED_AT,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight,
)
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight.schema.json"
DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"
RUNTIME_GENERATED_AT = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_PREFLIGHT_GENERATED_AT
EXPECTED_EVIDENCE_KINDS = frozenset(
    {
        "operator_decision_value_ref",
        "operator_identity_ref",
        "operator_signature_ref",
        "operator_reapproval_decision_receipt_ref",
    }
)
EXPECTED_REQUIREMENT_KINDS = frozenset(
    {
        "verifier_identity_ref",
        "verification_method_ref",
        "evidence_integrity_hash_ref",
        "source_ref_reachability_witness_ref",
        "decision_receipt_crosscheck_ref",
    }
)
FALSE_AUTHORITY_FIELDS = frozenset(
    {
        "verifier_ref_validated",
        "verifier_ref_bound",
        "verifier_identity_bound",
        "verification_method_bound",
        "evidence_integrity_hash_bound",
        "source_ref_reachability_witness_bound",
        "decision_receipt_crosscheck_bound",
        "verification_requirement_satisfied",
        "evidence_verified",
        "evidence_accepted",
        "evidence_rejected",
        "operator_value_bound",
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
RAW_PRIVATE_FIELD_NAMES = frozenset(
    {
        "raw_private_connector_payload",
        "raw_connector_payload",
        "private_connector_payload",
        "connector_response",
        "message_body",
        "email_body",
        "calendar_payload",
        "mailbox_payload",
        "raw_message",
        "raw_thread",
        "raw_calendar_event",
        "raw_task_payload",
        "raw_chat_log",
        "chat_log",
        "transcript",
        "credential",
        "credentials",
        "token",
        "secret",
        "private_key",
        "authorization",
        "cookie",
        "raw_operator_decision",
        "operator_decision_value",
        "operator_identity",
        "operator_signature",
        "raw_decision_receipt",
        "submitted_evidence_payload",
        "raw_submitted_evidence",
        "raw_verifier_payload",
        "verifier_payload",
        "verifier_execution_payload",
        "verifier_result",
        "submitted_value",
        "accepted_value",
        "verified_value",
    }
)
ALLOWED_POLICY_FIELD_NAMES = frozenset(
    {
        "private_payload_policy",
        "raw_private_payload_serialized",
        "secret_values_serialized",
        "verifier_validation_preflight_projection",
        "submitted_verifier_ref_projection",
        "verifier_execution_payload_projection",
        "verification_evidence_projection",
        "operator_decision_value_projection",
        "operator_identity_ref_projection",
        "operator_signature_ref_projection",
        "decision_receipt_projection",
    }
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantOperatorReapprovalDecisionReceiptValueBindingRecordVerifierExecutionPreflightValidation:
    """Validation result for verifier execution preflight."""

    valid: bool
    runtime_validated: bool
    verifier_execution_preflight_count: int
    submitted_verifier_ref_count: int
    verifier_execution_request_prepared_count: int
    verifier_execution_allowed_count: int
    verifier_execution_started_count: int
    verifier_execution_completed_count: int
    verifier_result_count: int
    validated_verifier_ref_count: int
    verified_evidence_count: int
    accepted_evidence_count: int
    authority_grant_count: int
    assurance_outcome: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
) -> PersonalAssistantOperatorReapprovalDecisionReceiptValueBindingRecordVerifierExecutionPreflightValidation:
    """Validate runtime verifier execution preflight."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "operator verifier execution preflight schema", errors)
    receipt_schema = _load_json_object(receipt_schema_path, "receipt schema", errors)
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight(
        generated_at=RUNTIME_GENERATED_AT,
    )
    summary = _mapping(envelope.get("summary"))
    assurance = _mapping(envelope.get("assurance"))
    if schema:
        errors.extend(_validate_schema_instance(schema, envelope))
    errors.extend(_validate_verifier_execution_preflight_semantics(envelope, receipt_schema))
    _scan_private_or_secret_payload(envelope, errors, path="$runtime")
    return PersonalAssistantOperatorReapprovalDecisionReceiptValueBindingRecordVerifierExecutionPreflightValidation(
        valid=not errors,
        runtime_validated=not errors,
        verifier_execution_preflight_count=int(envelope.get("verifier_execution_preflight_count", 0)),
        submitted_verifier_ref_count=int(summary.get("submitted_verifier_ref_count", 0)),
        verifier_execution_request_prepared_count=int(summary.get("verifier_execution_request_prepared_count", 0)),
        verifier_execution_allowed_count=int(summary.get("verifier_execution_allowed_count", 0)),
        verifier_execution_started_count=int(summary.get("verifier_execution_started_count", 0)),
        verifier_execution_completed_count=int(summary.get("verifier_execution_completed_count", 0)),
        verifier_result_count=int(summary.get("verifier_result_count", 0)),
        validated_verifier_ref_count=int(summary.get("validated_verifier_ref_count", 0)),
        verified_evidence_count=int(summary.get("verified_evidence_count", 0)),
        accepted_evidence_count=int(summary.get("accepted_evidence_count", 0)),
        authority_grant_count=int(summary.get("authority_grant_count", 0)),
        assurance_outcome=str(assurance.get("outcome", "")),
        errors=tuple(errors),
    )


def _validate_verifier_execution_preflight_semantics(
    envelope: Mapping[str, Any],
    receipt_schema: Mapping[str, Any],
) -> tuple[str, ...]:
    errors: list[str] = []
    expected_top = {
        "verifier_execution_preflight_state": "verifier_execution_requested_not_run_not_validated",
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "source_projection": "operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight",
    }
    for field_name, expected_value in expected_top.items():
        if envelope.get(field_name) != expected_value:
            errors.append(f"{field_name} must be {expected_value}")
    effect_boundary = _mapping(envelope.get("effect_boundary"))
    for field_name in (
        "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight_allowed",
        "verifier_validation_preflight_ref_binding_allowed",
        "verifier_execution_request_preparation_allowed",
        "verifier_execution_policy_check_allowed",
        "verifier_refs_present",
        "verifier_ref_only",
        "shape_scope_preflight_source_present",
    ):
        if effect_boundary.get(field_name) is not True:
            errors.append(f"effect_boundary.{field_name} must be true")
    _require_false_fields(
        effect_boundary,
        FALSE_AUTHORITY_FIELDS
        | {
            "raw_verifier_payload_present",
            "raw_evidence_payload_present",
            "raw_operator_value_present",
            "verifier_execution_allowed",
            "verifier_execution_started",
            "verifier_execution_completed",
            "verifier_result_present",
        },
        "effect_boundary",
        errors,
    )
    _require_private_payload_policy(_mapping(envelope.get("private_payload_policy")), errors)

    records = envelope.get("verifier_execution_preflights")
    if not isinstance(records, list):
        errors.append("verifier_execution_preflights must be a list")
        return tuple(errors)
    if envelope.get("verifier_execution_preflight_count") != len(records):
        errors.append("verifier_execution_preflight_count must equal verifier_execution_preflights length")
    record_ids: list[str] = []
    receipt_ids: list[str] = []
    coverage: dict[str, set[str]] = {}
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"verifier_execution_preflights[{index}] must be an object")
            continue
        record_ids.append(str(record.get("verifier_execution_preflight_record_id", "")))
        evidence_kind = str(record.get("evidence_kind", ""))
        requirement_kind = str(record.get("requirement_kind", ""))
        coverage.setdefault(evidence_kind, set()).add(requirement_kind)
        _require_source_ref(index, _mapping(record.get("verifier_validation_preflight_ref")), errors)
        _require_verifier_execution_preflight(index, _mapping(record.get("verifier_execution_preflight")), record, errors)
        _require_false_fields(
            _mapping(record.get("authority_status")),
            FALSE_AUTHORITY_FIELDS
            - {
                "verifier_ref_validated",
                "verifier_ref_bound",
                "verification_requirement_satisfied",
                "evidence_verified",
                "evidence_accepted",
                "evidence_rejected",
            },
            f"verifier_execution_preflights[{index}].authority_status",
            errors,
        )
        receipt = _mapping(record.get("receipt"))
        if receipt_schema:
            errors.extend(
                f"verifier_execution_preflights[{index}].receipt {message}"
                for message in _validate_schema_instance(dict(receipt_schema), receipt)
            )
        errors.extend(
            f"verifier_execution_preflights[{index}].receipt {message}"
            for message in validate_personal_assistant_receipt_payload(receipt)
        )
        if receipt.get("decision") != "blocked" or receipt.get("outcome") != "AwaitingEvidence":
            errors.append(f"verifier_execution_preflights[{index}].receipt must remain blocked AwaitingEvidence")
        metadata = _mapping(receipt.get("metadata"))
        if metadata.get("operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight_is_execution") is not False:
            errors.append(f"verifier_execution_preflights[{index}].receipt.metadata execution flag must be false")
        _require_false_fields(
            metadata,
            FALSE_AUTHORITY_FIELDS
            | {
                "raw_verifier_payload_present",
                "verifier_execution_allowed",
                "verifier_execution_started",
                "verifier_execution_completed",
                "verifier_result_present",
            },
            f"verifier_execution_preflights[{index}].receipt.metadata",
            errors,
        )
        receipt_ids.append(str(receipt.get("receipt_id", "")))
    if set(coverage) != EXPECTED_EVIDENCE_KINDS:
        errors.append("verifier_execution_preflights must cover all governed evidence kinds")
    for evidence_kind, requirement_kinds in coverage.items():
        if requirement_kinds != EXPECTED_REQUIREMENT_KINDS:
            errors.append(f"verifier_execution_preflights for {evidence_kind} must cover all verifier requirement kinds")
    if envelope.get("verifier_execution_preflight_record_ids") != record_ids:
        errors.append("verifier_execution_preflight_record_ids must match record order")
    if envelope.get("receipt_ids") != receipt_ids:
        errors.append("receipt_ids must match record receipts")
    _require_summary(envelope, records, errors)
    assurance = _mapping(envelope.get("assurance"))
    if assurance.get("outcome") != "AwaitingEvidence":
        errors.append("assurance.outcome must remain AwaitingEvidence")
    for field_name in (
        "ready_for_verifier_execution",
        "ready_for_evidence_verification",
        "ready_for_evidence_acceptance",
        "ready_for_binding_record_admission",
        "ready_for_execution_worker_admission",
        "ready_for_live_execution",
        "ready_for_customer_readiness_claim",
        "authority_drift_detected",
    ):
        if assurance.get(field_name) is not False:
            errors.append(f"assurance.{field_name} must be false")
    return tuple(errors)


def _require_source_ref(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    expected = {
        "source_validation_preflight_state": "verifier_refs_scoped_for_validation_not_validated_not_bound",
        "source_outcome": "AwaitingEvidence",
        "source_shape_checked": True,
        "source_scope_checked": True,
        "source_verifier_ref_validated": False,
        "source_verifier_ref_bound": False,
        "source_evidence_verified": False,
        "source_authority_granted": False,
    }
    for field_name, expected_value in expected.items():
        if payload.get(field_name) != expected_value:
            errors.append(f"verifier_execution_preflights[{index}].verifier_validation_preflight_ref.{field_name} must be {expected_value}")


def _require_verifier_execution_preflight(
    index: int,
    payload: Mapping[str, Any],
    record: Mapping[str, Any],
    errors: list[str],
) -> None:
    expected_true = {
        "verifier_ref_only",
        "verifier_ref_present",
        "execution_preflight_created",
        "verifier_execution_request_prepared",
        "operator_approval_required",
    }
    expected_false = {
        "raw_verifier_payload_present",
        "verifier_execution_allowed",
        "verifier_execution_started",
        "verifier_execution_completed",
        "verifier_result_present",
        "verifier_ref_validated",
        "verifier_ref_bound",
        "verification_requirement_satisfied",
        "evidence_verified",
        "evidence_accepted",
        "evidence_rejected",
    }
    if payload.get("submitted_verifier_ref") != record.get("submitted_verifier_ref"):
        errors.append(f"verifier_execution_preflights[{index}].verifier_execution_preflight submitted ref must match record")
    if payload.get("requirement_kind") != record.get("requirement_kind"):
        errors.append(f"verifier_execution_preflights[{index}].verifier_execution_preflight requirement kind must match record")
    for field_name in expected_true:
        if payload.get(field_name) is not True:
            errors.append(f"verifier_execution_preflights[{index}].verifier_execution_preflight.{field_name} must be true")
    for field_name in expected_false:
        if payload.get(field_name) is not False:
            errors.append(f"verifier_execution_preflights[{index}].verifier_execution_preflight.{field_name} must be false")
    if payload.get("blocking_reason") != "operator_must_approve_separate_governed_verifier_execution":
        errors.append(f"verifier_execution_preflights[{index}].verifier_execution_preflight blocking_reason must remain approval required")


def _require_summary(envelope: Mapping[str, Any], records: list[Any], errors: list[str]) -> None:
    summary = _mapping(envelope.get("summary"))
    expected = {
        "verifier_execution_preflight_count": len(records),
        "submitted_verifier_ref_count": len(records),
        "verifier_execution_request_prepared_count": len(records),
        "verifier_execution_allowed_count": 0,
        "verifier_execution_started_count": 0,
        "verifier_execution_completed_count": 0,
        "verifier_result_count": 0,
        "validated_verifier_ref_count": 0,
        "bound_verifier_ref_count": 0,
        "satisfied_verification_requirement_count": 0,
        "verified_evidence_count": 0,
        "accepted_evidence_count": 0,
        "rejected_evidence_count": 0,
        "authority_grant_count": 0,
        "binding_record_creation_count": 0,
    }
    for field_name, expected_value in expected.items():
        if summary.get(field_name) != expected_value:
            errors.append(f"summary.{field_name} must be {expected_value}")


def _require_private_payload_policy(payload: Mapping[str, Any], errors: list[str]) -> None:
    expected = {
        "raw_private_payload_serialized": False,
        "secret_values_serialized": False,
        "verifier_validation_preflight_projection": "ref_only",
        "submitted_verifier_ref_projection": "ref_only",
        "verifier_execution_payload_projection": "absent",
        "verification_evidence_projection": "absent",
        "operator_decision_value_projection": "absent",
        "operator_identity_ref_projection": "absent",
        "operator_signature_ref_projection": "absent",
        "decision_receipt_projection": "absent",
    }
    for field_name, expected_value in expected.items():
        if payload.get(field_name) != expected_value:
            errors.append(f"private_payload_policy.{field_name} must be {expected_value}")


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


def _scan_private_or_secret_payload(payload: Any, errors: list[str], *, path: str) -> None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            normalized_key = str(key).lower()
            if normalized_key not in ALLOWED_POLICY_FIELD_NAMES and normalized_key in RAW_PRIVATE_FIELD_NAMES:
                errors.append(f"{path}.{key}: raw private or secret field is forbidden")
            _scan_private_or_secret_payload(value, errors, path=f"{path}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _scan_private_or_secret_payload(value, errors, path=f"{path}[{index}]")
    elif isinstance(payload, str) and any(pattern.search(payload) for pattern in SECRET_VALUE_PATTERNS):
        errors.append(f"{path}: secret-like value must not be serialized")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--receipt-schema", type=Path, default=DEFAULT_RECEIPT_SCHEMA)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight(
        schema_path=args.schema,
        receipt_schema_path=args.receipt_schema,
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print("PERSONAL ASSISTANT OPERATOR REAPPROVAL DECISION RECEIPT VALUE BINDING RECORD VERIFIER EXECUTION PREFLIGHT VALID")
    else:
        for error in result.errors:
            print(f"[ERROR] {error}", file=sys.stderr)
    return 0 if result.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())

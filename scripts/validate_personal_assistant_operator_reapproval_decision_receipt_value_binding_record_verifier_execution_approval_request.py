#!/usr/bin/env python3
"""Validate operator value-binding verifier execution approval request."""

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
    DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_APPROVAL_REQUEST_GENERATED_AT,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request,
)
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request.schema.json"
)
DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"
RUNTIME_GENERATED_AT = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_APPROVAL_REQUEST_GENERATED_AT
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
        "operator_decision_present",
        "operator_approval_granted",
        "operator_approval_rejected",
        "verifier_execution_allowed",
        "verifier_execution_started",
        "verifier_result_present",
        "verifier_ref_validated",
        "evidence_verified",
        "evidence_accepted",
        "authority_granted",
        "binding_record_created",
        "execution_worker_admission_allowed",
        "dispatch_allowed",
        "live_connector_execution_allowed",
        "connector_mutation_allowed",
        "system_of_record_write_allowed",
        "memory_write_allowed",
    }
)
FALSE_APPROVAL_REQUEST_FIELDS = frozenset(
    {
        "operator_decision_present",
        "operator_approval_granted",
        "operator_approval_rejected",
        "ready_for_operator_decision",
        "ready_for_verifier_execution",
        "verifier_execution_allowed",
        "verifier_execution_started",
        "verifier_result_present",
        "verifier_ref_validated",
        "evidence_verified",
        "evidence_accepted",
        "authority_granted",
    }
)
FALSE_RECEIPT_METADATA_FIELDS = frozenset(
    {
        "operator_decision_present",
        "operator_approval_granted",
        "verifier_execution_allowed",
        "verifier_execution_started",
        "verifier_result_present",
        "verifier_ref_validated",
        "evidence_verified",
        "evidence_accepted",
        "authority_granted",
        "execution_worker_admission_allowed",
        "dispatch_allowed",
        "live_connector_execution_allowed",
        "connector_mutation_allowed",
        "external_write_allowed",
        "system_of_record_write_allowed",
        "memory_write_allowed",
        "money_legal_public_action_allowed",
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
        "verifier_execution_preflight_projection",
        "submitted_verifier_ref_projection",
        "approval_request_projection",
        "operator_decision_value_projection",
        "operator_identity_ref_projection",
        "operator_signature_ref_projection",
        "verifier_execution_payload_projection",
        "verification_evidence_projection",
        "decision_receipt_projection",
    }
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantOperatorReapprovalDecisionReceiptValueBindingRecordVerifierExecutionApprovalRequestValidation:
    """Validation result for verifier execution approval request."""

    valid: bool
    runtime_validated: bool
    verifier_execution_approval_request_count: int
    approval_requested_count: int
    operator_decision_present_count: int
    operator_approval_grant_count: int
    operator_approval_rejection_count: int
    verifier_execution_allowed_count: int
    verifier_execution_started_count: int
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


def validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
) -> PersonalAssistantOperatorReapprovalDecisionReceiptValueBindingRecordVerifierExecutionApprovalRequestValidation:
    """Validate runtime verifier execution approval request."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "operator verifier execution approval request schema", errors)
    receipt_schema = _load_json_object(receipt_schema_path, "receipt schema", errors)
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request(
        generated_at=RUNTIME_GENERATED_AT,
    )
    summary = _mapping(envelope.get("summary"))
    assurance = _mapping(envelope.get("assurance"))
    if schema:
        errors.extend(_validate_schema_instance(schema, envelope))
    errors.extend(_validate_verifier_execution_approval_request_semantics(envelope, receipt_schema))
    _scan_private_or_secret_payload(envelope, errors, path="$runtime")
    return PersonalAssistantOperatorReapprovalDecisionReceiptValueBindingRecordVerifierExecutionApprovalRequestValidation(
        valid=not errors,
        runtime_validated=not errors,
        verifier_execution_approval_request_count=int(envelope.get("verifier_execution_approval_request_count", 0)),
        approval_requested_count=int(summary.get("approval_requested_count", 0)),
        operator_decision_present_count=int(summary.get("operator_decision_present_count", 0)),
        operator_approval_grant_count=int(summary.get("operator_approval_grant_count", 0)),
        operator_approval_rejection_count=int(summary.get("operator_approval_rejection_count", 0)),
        verifier_execution_allowed_count=int(summary.get("verifier_execution_allowed_count", 0)),
        verifier_execution_started_count=int(summary.get("verifier_execution_started_count", 0)),
        verifier_result_count=int(summary.get("verifier_result_count", 0)),
        validated_verifier_ref_count=int(summary.get("validated_verifier_ref_count", 0)),
        verified_evidence_count=int(summary.get("verified_evidence_count", 0)),
        accepted_evidence_count=int(summary.get("accepted_evidence_count", 0)),
        authority_grant_count=int(summary.get("authority_grant_count", 0)),
        assurance_outcome=str(assurance.get("outcome", "")),
        errors=tuple(errors),
    )


def _validate_verifier_execution_approval_request_semantics(
    envelope: Mapping[str, Any],
    receipt_schema: Mapping[str, Any],
) -> tuple[str, ...]:
    errors: list[str] = []
    expected_top = {
        "approval_request_state": "approval_requested_not_decided_not_run",
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "source_projection": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight",
    }
    for field_name, expected_value in expected_top.items():
        if envelope.get(field_name) != expected_value:
            errors.append(f"{field_name} must be {expected_value}")
    effect_boundary = _mapping(envelope.get("effect_boundary"))
    for field_name in (
        "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request_allowed",
        "verifier_execution_preflight_ref_binding_allowed",
        "operator_approval_request_preparation_allowed",
        "verifier_execution_requests_present",
        "verifier_refs_present",
        "verifier_ref_only",
    ):
        if effect_boundary.get(field_name) is not True:
            errors.append(f"effect_boundary.{field_name} must be true")
    _require_false_fields(
        effect_boundary,
        (
            FALSE_AUTHORITY_FIELDS
            | {
            "operator_approval_decision_present",
            "operator_approval_value_present",
            "verifier_execution_completed",
            "evidence_rejected",
            "deployment_mutation_allowed",
            "nested_mind_live_activation_allowed",
            "public_readiness_claim_allowed",
            }
        )
        - {"operator_decision_present", "operator_approval_rejected", "binding_record_created"},
        "effect_boundary",
        errors,
    )
    _require_private_payload_policy(_mapping(envelope.get("private_payload_policy")), errors)

    records = envelope.get("verifier_execution_approval_requests")
    if not isinstance(records, list):
        errors.append("verifier_execution_approval_requests must be a list")
        return tuple(errors)
    if envelope.get("verifier_execution_approval_request_count") != len(records):
        errors.append("verifier_execution_approval_request_count must equal verifier_execution_approval_requests length")
    item_ids: list[str] = []
    receipt_ids: list[str] = []
    coverage: dict[str, set[str]] = {}
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"verifier_execution_approval_requests[{index}] must be an object")
            continue
        item_ids.append(str(record.get("verifier_execution_approval_request_item_id", "")))
        evidence_kind = str(record.get("evidence_kind", ""))
        requirement_kind = str(record.get("requirement_kind", ""))
        coverage.setdefault(evidence_kind, set()).add(requirement_kind)
        _require_source_ref(index, _mapping(record.get("verifier_execution_preflight_ref")), errors)
        _require_approval_request(index, _mapping(record.get("approval_request")), errors)
        _require_false_fields(
            _mapping(record.get("authority_status")),
            FALSE_AUTHORITY_FIELDS
            - {
                "operator_decision_present",
                "operator_approval_granted",
                "operator_approval_rejected",
                "verifier_execution_allowed",
                "verifier_execution_started",
                "verifier_result_present",
                "verifier_ref_validated",
                "evidence_verified",
                "evidence_accepted",
            },
            f"verifier_execution_approval_requests[{index}].authority_status",
            errors,
        )
        receipt = _mapping(record.get("receipt"))
        if receipt_schema:
            errors.extend(
                f"verifier_execution_approval_requests[{index}].receipt {message}"
                for message in _validate_schema_instance(dict(receipt_schema), receipt)
            )
        errors.extend(
            f"verifier_execution_approval_requests[{index}].receipt {message}"
            for message in validate_personal_assistant_receipt_payload(receipt)
        )
        if receipt.get("decision") != "blocked" or receipt.get("outcome") != "AwaitingEvidence":
            errors.append(f"verifier_execution_approval_requests[{index}].receipt must remain blocked AwaitingEvidence")
        metadata = _mapping(receipt.get("metadata"))
        if metadata.get("operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request_is_execution") is not False:
            errors.append(f"verifier_execution_approval_requests[{index}].receipt.metadata execution flag must be false")
        _require_false_fields(metadata, FALSE_RECEIPT_METADATA_FIELDS, f"verifier_execution_approval_requests[{index}].receipt.metadata", errors)
        receipt_ids.append(str(receipt.get("receipt_id", "")))
    if set(coverage) != EXPECTED_EVIDENCE_KINDS:
        errors.append("verifier_execution_approval_requests must cover all governed evidence kinds")
    for evidence_kind, requirement_kinds in coverage.items():
        if requirement_kinds != EXPECTED_REQUIREMENT_KINDS:
            errors.append(f"verifier_execution_approval_requests for {evidence_kind} must cover all verifier requirement kinds")
    if envelope.get("verifier_execution_approval_request_item_ids") != item_ids:
        errors.append("verifier_execution_approval_request_item_ids must match item order")
    if envelope.get("receipt_ids") != receipt_ids:
        errors.append("receipt_ids must match item receipts")
    _require_summary(envelope, records, errors)
    assurance = _mapping(envelope.get("assurance"))
    if assurance.get("outcome") != "AwaitingEvidence":
        errors.append("assurance.outcome must remain AwaitingEvidence")
    for field_name in (
        "ready_for_operator_decision",
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
        "source_preflight_state": "verifier_execution_requested_not_run_not_validated",
        "source_outcome": "AwaitingEvidence",
        "source_verifier_execution_request_prepared": True,
        "source_verifier_execution_allowed": False,
        "source_verifier_execution_started": False,
        "source_verifier_result_present": False,
        "source_verifier_ref_validated": False,
        "source_evidence_verified": False,
        "source_authority_granted": False,
    }
    for field_name, expected_value in expected.items():
        if payload.get(field_name) != expected_value:
            errors.append(f"verifier_execution_approval_requests[{index}].verifier_execution_preflight_ref.{field_name} must be {expected_value}")


def _require_approval_request(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    for field_name in ("approval_requested", "operator_decision_required"):
        if payload.get(field_name) is not True:
            errors.append(f"verifier_execution_approval_requests[{index}].approval_request.{field_name} must be true")
    _require_false_fields(payload, FALSE_APPROVAL_REQUEST_FIELDS, f"verifier_execution_approval_requests[{index}].approval_request", errors)
    if payload.get("blocking_reason") != "operator_decision_not_present":
        errors.append(f"verifier_execution_approval_requests[{index}].approval_request blocking_reason must remain operator_decision_not_present")


def _require_summary(envelope: Mapping[str, Any], records: list[Any], errors: list[str]) -> None:
    summary = _mapping(envelope.get("summary"))
    expected = {
        "verifier_execution_approval_request_count": len(records),
        "approval_requested_count": len(records),
        "operator_decision_present_count": 0,
        "operator_approval_grant_count": 0,
        "operator_approval_rejection_count": 0,
        "verifier_execution_allowed_count": 0,
        "verifier_execution_started_count": 0,
        "verifier_result_count": 0,
        "validated_verifier_ref_count": 0,
        "verified_evidence_count": 0,
        "accepted_evidence_count": 0,
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
        "verifier_execution_preflight_projection": "ref_only",
        "submitted_verifier_ref_projection": "ref_only",
        "approval_request_projection": "request_metadata_only",
        "operator_decision_value_projection": "absent",
        "operator_identity_ref_projection": "absent",
        "operator_signature_ref_projection": "absent",
        "verifier_execution_payload_projection": "absent",
        "verification_evidence_projection": "absent",
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

    result = validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request(
        schema_path=args.schema,
        receipt_schema_path=args.receipt_schema,
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print("PERSONAL ASSISTANT OPERATOR REAPPROVAL DECISION RECEIPT VALUE BINDING RECORD VERIFIER EXECUTION APPROVAL REQUEST VALID")
    else:
        for error in result.errors:
            print(f"[ERROR] {error}", file=sys.stderr)
    return 0 if result.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())

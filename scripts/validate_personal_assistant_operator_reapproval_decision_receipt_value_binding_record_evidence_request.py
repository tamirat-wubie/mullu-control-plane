#!/usr/bin/env python3
"""Validate personal-assistant operator value-binding record evidence requests.

Purpose: prove request-only evidence slots are emitted after value-binding
record admission preflight blocks missing operator evidence.
Governance scope: admission-preflight refs, request-only operator evidence
slots, receipt conformance, private-payload redaction, and Foundation Mode
no-effect boundaries.
Dependencies: personal-assistant value-binding record evidence request runtime
helper, schema validators, and receipt validator.
Invariants:
  - Evidence requests are not evidence submissions or accepted evidence.
  - Raw operator values, identities, signatures, decision receipts, connector
    payloads, and secrets are not serialized.
  - Binding-record admission, execution-worker admission, dispatch, live
    connector execution, memory writes, system-of-record writes, and readiness
    claims remain false.
"""

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
    DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_EVIDENCE_REQUEST_GENERATED_AT,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request,
)
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = (
    REPO_ROOT / "schemas" / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request.schema.json"
)
DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"
RUNTIME_GENERATED_AT = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_EVIDENCE_REQUEST_GENERATED_AT
EXPECTED_EVIDENCE_KINDS = frozenset(
    {
        "operator_decision_value_ref",
        "operator_identity_ref",
        "operator_signature_ref",
        "operator_reapproval_decision_receipt_ref",
    }
)
EXPECTED_DECISION_VALUES = ("approved", "rejected", "revised", "expired")
TRUE_EFFECT_BOUNDARY_FIELDS = frozenset(
    {
        "operator_reapproval_decision_receipt_value_binding_record_evidence_request_allowed",
        "value_binding_record_admission_preflight_ref_binding_allowed",
        "operator_evidence_slot_request_allowed",
        "operator_input_request_allowed",
        "operator_submitted_value_ref_required",
        "operator_identity_ref_required",
        "operator_signature_ref_required",
        "decision_receipt_ref_required",
        "evidence_request_issued",
    }
)
FALSE_EFFECT_BOUNDARY_FIELDS = frozenset(
    {
        "evidence_request_is_submission",
        "evidence_request_is_acceptance",
        "evidence_submitted",
        "evidence_accepted",
        "evidence_rejected",
        "operator_value_collected",
        "explicit_operator_value_present",
        "operator_value_bound",
        "operator_identity_ref_bound",
        "operator_signature_ref_bound",
        "decision_receipt_ref_bound",
        "accepted_value_present",
        "binding_record_candidate_accepted",
        "binding_record_created",
        "binding_record_admitted",
        "admission_approved",
        "authority_granted",
        "execution_worker_admission_allowed",
        "dispatch_allowed",
        "dispatch_lease_active",
        "live_connector_receipt_present",
        "live_connector_execution_allowed",
        "external_send_allowed",
        "calendar_write_allowed",
        "task_write_allowed",
        "memory_write_allowed",
        "connector_mutation_allowed",
        "system_of_record_write_allowed",
        "deployment_mutation_allowed",
        "nested_mind_live_activation_allowed",
        "public_readiness_claim_allowed",
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
    }
)
ALLOWED_POLICY_FIELD_NAMES = frozenset(
    {
        "private_payload_policy",
        "raw_private_payload_serialized",
        "secret_values_serialized",
        "value_binding_record_admission_preflight_projection",
        "operator_decision_value_projection",
        "operator_identity_ref_projection",
        "operator_signature_ref_projection",
        "decision_receipt_projection",
        "evidence_submission_projection",
    }
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantOperatorReapprovalDecisionReceiptValueBindingRecordEvidenceRequestValidation:
    """Validation result for request-only operator value-binding evidence slots."""

    valid: bool
    runtime_validated: bool
    evidence_request_count: int
    requested_slot_count: int
    submitted_evidence_count: int
    accepted_evidence_count: int
    assurance_outcome: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        rendered = asdict(self)
        rendered["errors"] = list(self.errors)
        return rendered


def validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
) -> PersonalAssistantOperatorReapprovalDecisionReceiptValueBindingRecordEvidenceRequestValidation:
    """Validate runtime value-binding record evidence request slots."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "operator reapproval value-binding record evidence request schema", errors)
    receipt_schema = _load_json_object(receipt_schema_path, "receipt schema", errors)
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request(
        generated_at=RUNTIME_GENERATED_AT,
    )
    assurance = _mapping(envelope.get("assurance"))
    summary = _mapping(envelope.get("summary"))
    if schema:
        errors.extend(_validate_schema_instance(schema, envelope))
    errors.extend(_validate_value_binding_record_evidence_request_semantics(envelope, receipt_schema))
    _scan_private_or_secret_payload(envelope, errors, path="$runtime")
    return PersonalAssistantOperatorReapprovalDecisionReceiptValueBindingRecordEvidenceRequestValidation(
        valid=not errors,
        runtime_validated=not errors,
        evidence_request_count=int(envelope.get("evidence_request_count", 0)),
        requested_slot_count=int(summary.get("requested_slot_count", 0)),
        submitted_evidence_count=int(summary.get("submitted_evidence_count", 0)),
        accepted_evidence_count=int(summary.get("accepted_evidence_count", 0)),
        assurance_outcome=str(assurance.get("outcome", "")),
        errors=tuple(errors),
    )


def _validate_value_binding_record_evidence_request_semantics(
    envelope: Mapping[str, Any],
    receipt_schema: Mapping[str, Any],
) -> tuple[str, ...]:
    errors: list[str] = []
    if envelope.get("decision") != "blocked":
        errors.append("decision must remain blocked")
    if envelope.get("outcome") != "AwaitingEvidence":
        errors.append("outcome must remain AwaitingEvidence")
    if envelope.get("evidence_request_state") != "requested_not_submitted":
        errors.append("evidence_request_state must remain requested_not_submitted")
    _require_true_fields(_mapping(envelope.get("effect_boundary")), TRUE_EFFECT_BOUNDARY_FIELDS, "effect_boundary", errors)
    _require_false_fields(_mapping(envelope.get("effect_boundary")), FALSE_EFFECT_BOUNDARY_FIELDS, "effect_boundary", errors)
    _require_private_payload_policy(_mapping(envelope.get("private_payload_policy")), errors)

    requests = envelope.get("evidence_requests")
    if not isinstance(requests, list):
        errors.append("evidence_requests must be a list")
        return tuple(errors)
    if envelope.get("evidence_request_count") != len(requests):
        errors.append("evidence_request_count must equal evidence_requests length")
    request_ids: list[str] = []
    source_preflight_ids: list[str] = []
    receipt_ids: list[str] = []
    grouped_kinds: dict[str, set[str]] = {}
    for index, request_slot in enumerate(requests):
        if not isinstance(request_slot, dict):
            errors.append(f"evidence_requests[{index}] must be an object")
            continue
        request_ids.append(str(request_slot.get("evidence_request_id", "")))
        source_preflight_id = str(request_slot.get("source_admission_preflight_id", ""))
        source_preflight_ids.append(source_preflight_id)
        grouped_kinds.setdefault(source_preflight_id, set()).add(str(request_slot.get("evidence_kind", "")))
        if request_slot.get("evidence_kind") not in EXPECTED_EVIDENCE_KINDS:
            errors.append(f"evidence_requests[{index}].evidence_kind must be governed evidence kind")
        _require_source_preflight_ref(index, _mapping(request_slot.get("source_admission_preflight_ref")), errors)
        _require_request_contract(index, _mapping(request_slot.get("request_contract")), errors)
        _require_submission_state(index, _mapping(request_slot.get("submission_state")), errors)
        receipt = _mapping(request_slot.get("receipt"))
        if receipt_schema:
            errors.extend(
                f"evidence_requests[{index}].receipt {message}"
                for message in _validate_schema_instance(dict(receipt_schema), receipt)
            )
        errors.extend(f"evidence_requests[{index}].receipt {message}" for message in validate_personal_assistant_receipt_payload(receipt))
        if receipt.get("decision") != "blocked":
            errors.append(f"evidence_requests[{index}].receipt.decision must be blocked")
        if receipt.get("outcome") != "AwaitingEvidence":
            errors.append(f"evidence_requests[{index}].receipt.outcome must be AwaitingEvidence")
        if receipt.get("approval_ref") != request_slot.get("approval_id"):
            errors.append(f"evidence_requests[{index}].receipt.approval_ref must match approval_id")
        metadata = _mapping(receipt.get("metadata"))
        if metadata.get("operator_reapproval_decision_receipt_value_binding_record_evidence_request_is_execution") is not False:
            errors.append(
                "evidence_requests["
                f"{index}].receipt.metadata.operator_reapproval_decision_receipt_value_binding_record_evidence_request_is_execution must be false"
            )
        if metadata.get("request_only") is not True or metadata.get("raw_value_requested") is not False:
            errors.append(f"evidence_requests[{index}].receipt.metadata must remain request-only and ref-only")
        _require_false_fields(
            metadata,
            frozenset(
                {
                    "operator_value_collected",
                    "explicit_operator_value_present",
                    "operator_value_bound",
                    "operator_identity_ref_bound",
                    "operator_signature_ref_bound",
                    "decision_receipt_ref_bound",
                    "accepted_value_present",
                    "binding_record_candidate_accepted",
                    "binding_record_created",
                    "binding_record_admitted",
                    "admission_approved",
                    "authority_granted",
                    "execution_worker_admission_allowed",
                    "dispatch_allowed",
                    "dispatch_lease_active",
                    "live_connector_receipt_present",
                    "live_connector_execution_allowed",
                    "connector_mutation_allowed",
                    "external_write_allowed",
                    "system_of_record_write_allowed",
                    "memory_write_allowed",
                    "money_legal_public_action_allowed",
                }
            ),
            f"evidence_requests[{index}].receipt.metadata",
            errors,
        )
        receipt_ids.append(str(receipt.get("receipt_id", "")))
    if envelope.get("evidence_request_ids") != request_ids:
        errors.append("evidence_request_ids must match request order")
    if envelope.get("source_admission_preflight_ids") != source_preflight_ids:
        errors.append("source_admission_preflight_ids must match request order")
    if envelope.get("receipt_ids") != receipt_ids:
        errors.append("receipt_ids must match request receipts")
    for source_preflight_id, evidence_kinds in grouped_kinds.items():
        if evidence_kinds != EXPECTED_EVIDENCE_KINDS:
            errors.append(f"{source_preflight_id}: evidence request kinds must cover all required slots")
    _require_summary(envelope, requests, errors)
    assurance = _mapping(envelope.get("assurance"))
    if assurance.get("outcome") != "AwaitingEvidence":
        errors.append("assurance.outcome must remain AwaitingEvidence")
    for field_name in (
        "ready_for_evidence_submission",
        "ready_for_binding_record_admission",
        "ready_for_execution_worker_admission",
        "ready_for_live_execution",
        "ready_for_customer_readiness_claim",
        "authority_drift_detected",
    ):
        if assurance.get(field_name) is not False:
            errors.append(f"assurance.{field_name} must be false")
    metadata = _mapping(envelope.get("metadata"))
    if metadata.get("request_only") is not True:
        errors.append("metadata.request_only must be true")
    _require_false_fields(
        metadata,
        FALSE_EFFECT_BOUNDARY_FIELDS
        - {"evidence_request_is_submission", "evidence_request_is_acceptance", "evidence_submitted", "evidence_accepted", "evidence_rejected", "dispatch_lease_active", "live_connector_receipt_present"},
        "metadata",
        errors,
    )
    return tuple(errors)


def _require_source_preflight_ref(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    if payload.get("source_outcome") != "GovernanceBlocked":
        errors.append(f"evidence_requests[{index}].source_admission_preflight_ref.source_outcome must be GovernanceBlocked")
    for field_name in ("binding_record_created", "execution_worker_admission_allowed"):
        if payload.get(field_name) is not False:
            errors.append(f"evidence_requests[{index}].source_admission_preflight_ref.{field_name} must be false")


def _require_request_contract(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    expected = {
        "request_state": "requested",
        "proof_state": "Unknown",
        "required": True,
        "request_only": True,
        "ref_only": True,
        "raw_value_requested": False,
        "raw_payload_requested": False,
        "evidence_submission_required_later": True,
    }
    for field_name, expected_value in expected.items():
        if payload.get(field_name) != expected_value:
            errors.append(f"evidence_requests[{index}].request_contract.{field_name} must be {expected_value!r}")
    if tuple(payload.get("allowed_decision_values", ())) != EXPECTED_DECISION_VALUES:
        errors.append(f"evidence_requests[{index}].request_contract.allowed_decision_values must match policy")


def _require_submission_state(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    _require_false_fields(
        payload,
        frozenset(
            {
                "evidence_submitted",
                "evidence_accepted",
                "evidence_rejected",
                "requirement_satisfied",
                "authority_granted",
            }
        ),
        f"evidence_requests[{index}].submission_state",
        errors,
    )
    for field_name in ("submitted_evidence_refs", "accepted_evidence_refs", "rejected_evidence_refs"):
        if payload.get(field_name) != []:
            errors.append(f"evidence_requests[{index}].submission_state.{field_name} must remain empty")


def _require_summary(envelope: Mapping[str, Any], requests: list[Any], errors: list[str]) -> None:
    summary = _mapping(envelope.get("summary"))
    request_contracts = [_mapping(slot.get("request_contract")) for slot in requests if isinstance(slot, Mapping)]
    submission_states = [_mapping(slot.get("submission_state")) for slot in requests if isinstance(slot, Mapping)]
    expected_counts = {
        "evidence_request_count": len(requests),
        "requested_slot_count": sum(1 for contract in request_contracts if contract.get("request_state") == "requested"),
        "operator_input_required_count": len(requests),
        "unknown_proof_state_count": sum(1 for contract in request_contracts if contract.get("proof_state") == "Unknown"),
        "submitted_evidence_count": sum(1 for state in submission_states if state.get("evidence_submitted") is True),
        "accepted_evidence_count": sum(1 for state in submission_states if state.get("evidence_accepted") is True),
        "rejected_evidence_count": sum(1 for state in submission_states if state.get("evidence_rejected") is True),
        "satisfied_requirement_count": sum(1 for state in submission_states if state.get("requirement_satisfied") is True),
        "authority_grant_count": sum(1 for state in submission_states if state.get("authority_granted") is True),
        "binding_record_creation_count": sum(1 for slot in requests if isinstance(slot, Mapping) and slot.get("binding_record_created") is True),
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"summary.{field_name} must match evidence request slots")


def _require_private_payload_policy(payload: Mapping[str, Any], errors: list[str]) -> None:
    expected = {
        "raw_private_payload_serialized": False,
        "secret_values_serialized": False,
        "value_binding_record_admission_preflight_projection": "ref_only",
        "operator_decision_value_projection": "ref_request_only",
        "operator_identity_ref_projection": "ref_request_only",
        "operator_signature_ref_projection": "ref_request_only",
        "decision_receipt_projection": "ref_request_only",
        "evidence_submission_projection": "absent",
    }
    for field_name, expected_value in expected.items():
        if payload.get(field_name) != expected_value:
            errors.append(f"private_payload_policy.{field_name} must be {expected_value!r}")


def _require_true_fields(payload: Mapping[str, Any], field_names: frozenset[str], label: str, errors: list[str]) -> None:
    for field_name in sorted(field_names):
        if payload.get(field_name) is not True:
            errors.append(f"{label}.{field_name} must be true")


def _require_false_fields(payload: Mapping[str, Any], field_names: frozenset[str], label: str, errors: list[str]) -> None:
    for field_name in sorted(field_names):
        if payload.get(field_name) is not False:
            errors.append(f"{label}.{field_name} must be false")


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
    elif isinstance(payload, str):
        if any(pattern.search(payload) for pattern in SECRET_VALUE_PATTERNS):
            errors.append(f"{path}: secret-like value must not be serialized")


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        errors.append(f"{label} could not be read: {exc}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"{label} is invalid JSON: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} must be a JSON object")
        return {}
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--receipt-schema", type=Path, default=DEFAULT_RECEIPT_SCHEMA)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable validation result.")
    args = parser.parse_args(argv)

    validation = validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request(
        schema_path=args.schema,
        receipt_schema_path=args.receipt_schema,
    )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print("PERSONAL ASSISTANT OPERATOR REAPPROVAL DECISION RECEIPT VALUE BINDING RECORD EVIDENCE REQUEST VALID")
    else:
        for error in validation.errors:
            print(f"[FAIL] {error}", file=sys.stderr)
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())

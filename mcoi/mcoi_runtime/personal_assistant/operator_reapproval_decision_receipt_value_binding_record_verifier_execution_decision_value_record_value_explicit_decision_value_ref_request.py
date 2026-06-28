"""Purpose: verifier execution explicit decision value-ref request projection.
Governance scope: no-effect request for required operator decision value refs
after the missing-ref status ledger, without collecting, binding, storing,
admitting, or executing any value.
Dependencies: personal-assistant explicit decision value-ref status ledger
runtime and contracts.
Invariants:
  - Required value refs are requested as absent evidence refs, not accepted
    operator values.
  - The projection never binds operator identity, signature, decision value, or
    reapproval receipt values.
  - No operator value record, verifier execution, binding admission, or
    authority grant is produced.
  - Raw operator values, verifier payloads, and private connector payloads are
    never serialized.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger import (
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger,
)


DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_REQUEST_ID = (
    "pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request_foundation_001"
)
DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_REQUEST_GENERATED_AT = (
    "2026-06-14T02:05:00+00:00"
)

_REQUEST_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request_[a-z0-9][a-z0-9_:-]*$"
)
_REQUEST_ITEM_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request_item_[a-z0-9][a-z0-9_:-]*$"
)
_REQUIRED_VALUE_REFS = (
    "operator_decision_value_ref",
    "operator_identity_ref",
    "operator_signature_ref",
    "operator_reapproval_decision_receipt_ref",
)
_FALSE_FIELDS = {
    "explicit_decision_value_ref_request_satisfied": False,
    "explicit_decision_value_ref_status_ledger_satisfied": False,
    "explicit_decision_value_ref_preflight_satisfied": False,
    "explicit_decision_value_refs_collected": False,
    "explicit_decision_value_refs_present": False,
    "explicit_operator_decision_value_bound": False,
    "operator_value_record_created": False,
    "operator_value_record_admitted": False,
    "operator_decision_value_stored": False,
    "operator_decision_value_present": False,
    "operator_decision_value_collected": False,
    "operator_decision_value_submitted": False,
    "operator_decision_value_admitted": False,
    "operator_approval_granted": False,
    "operator_approval_rejected": False,
    "ready_for_verifier_execution": False,
    "verifier_execution_allowed": False,
    "verifier_execution_started": False,
    "verifier_execution_completed": False,
    "verifier_result_present": False,
    "binding_record_created": False,
    "binding_record_admitted": False,
    "authority_granted": False,
    "execution_worker_admission_allowed": False,
    "dispatch_allowed": False,
    "dispatch_lease_active": False,
    "live_connector_execution_allowed": False,
    "connector_mutation_allowed": False,
    "system_of_record_write_allowed": False,
    "memory_write_allowed": False,
    "deployment_mutation_allowed": False,
    "nested_mind_live_activation_allowed": False,
    "public_readiness_claim_allowed": False,
}
_EFFECT_BOUNDARY = {
    "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request_allowed": True,
    "explicit_decision_value_ref_status_ledger_ref_binding_allowed": True,
    "explicit_decision_value_ref_request_projection_allowed": True,
    "required_value_refs_declared": True,
    "required_value_refs_requested": True,
    "required_value_refs_absent": True,
    "operator_decision_required": True,
    "operator_decision_value_required": True,
    "record_contract_ready": True,
    "verifier_ref_only": True,
    **_FALSE_FIELDS,
}
_PRIVATE_PAYLOAD_POLICY = {
    "raw_private_payload_serialized": False,
    "secret_values_serialized": False,
    "explicit_decision_value_ref_status_projection": "missing_ref_status_only",
    "explicit_decision_value_ref_request_projection": "request_metadata_only",
    "operator_decision_value_projection": "absent",
    "operator_value_record_projection": "absent",
    "verifier_execution_payload_projection": "absent",
}
_RAW_PRIVATE_FIELD_NAMES = {
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
    "raw_operator_value_record",
    "operator_value_record",
    "operator_identity",
    "operator_signature",
    "raw_decision_receipt",
    "raw_verifier_payload",
    "verifier_payload",
    "verifier_execution_payload",
    "verifier_result",
    "submitted_evidence_payload",
    "accepted_value",
    "verified_value",
}
_ALLOWED_POLICY_FIELD_NAMES = frozenset(_PRIVATE_PAYLOAD_POLICY) | {"private_payload_policy"}
_SECRET_VALUE_PATTERNS = (
    re.compile(r"sk_live_[A-Za-z0-9]+"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"ya29\.[A-Za-z0-9._-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"secret-(?:token|worker|key)-value", re.IGNORECASE),
)


def build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request(
    *,
    generated_at: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_REQUEST_GENERATED_AT,
    explicit_decision_value_ref_request_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_REQUEST_ID,
) -> dict[str, Any]:
    """Build deterministic no-effect explicit decision value-ref request."""

    return build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request_envelope(
        generated_at=generated_at,
        explicit_decision_value_ref_request_id=explicit_decision_value_ref_request_id,
        operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger=(
            build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger()
        ),
    )


def build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request_envelope(
    *,
    generated_at: str,
    operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger: Mapping[str, Any],
    explicit_decision_value_ref_request_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_REQUEST_ID,
) -> dict[str, Any]:
    """Build blocked value-ref request from missing-ref status ledger evidence."""

    timestamp = _require_non_empty_text(generated_at, "generated_at")
    request_id = _require_pattern(explicit_decision_value_ref_request_id, "explicit_decision_value_ref_request_id", _REQUEST_ID_PATTERN)
    source_envelope = _require_mapping(
        operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger,
        "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger",
    )
    _scan_private_or_secret_payload(source_envelope, path="operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger")
    _assert_value_ref_status_ledger_boundary(source_envelope)

    source_ledger_id = _require_non_empty_text(source_envelope.get("explicit_decision_value_ref_status_ledger_id"), "explicit_decision_value_ref_status_ledger_id")
    source_statuses = _require_sequence(source_envelope.get("required_ref_statuses"), "required_ref_statuses")
    ref_requests = [_ref_request(source_ledger_id, ref_name, source_statuses) for ref_name in _REQUIRED_VALUE_REFS]
    receipt = _request_receipt(
        receipt_id="pa_receipt_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request_foundation_001",
        timestamp=timestamp,
    )
    envelope = {
        "explicit_decision_value_ref_request_id": request_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger",
        "source_explicit_decision_value_ref_status_ledger_id": source_ledger_id,
        "explicit_decision_value_ref_request_state": "required_explicit_decision_value_refs_requested_not_collected",
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "required_ref_request_count": len(ref_requests),
        "required_ref_request_ids": [request["required_ref_request_id"] for request in ref_requests],
        "required_ref_requests": ref_requests,
        "receipt": receipt,
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "summary": _summary(ref_requests),
        "assurance": {
            "assurance_id": "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request_no_effect_assurance",
            "outcome": "AwaitingEvidence",
            "foundation_only": True,
            "request_projection_only": True,
            "required_value_refs_declared": True,
            "required_value_refs_requested": True,
            "required_value_refs_collected": False,
            "explicit_decision_value_ref_request_satisfied": False,
            "explicit_operator_decision_value_bound": False,
            "operator_decision_value_present": False,
            "operator_value_record_created": False,
            "verifier_execution_allowed": False,
            "authority_granted": False,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "blocking_reasons": [
                "operator_decision_value_ref_requested_not_collected",
                "operator_identity_ref_requested_not_collected",
                "operator_signature_ref_requested_not_collected",
                "operator_reapproval_decision_receipt_ref_requested_not_collected",
                "operator_value_record_not_created",
                "verifier_execution_not_authorized",
                "execution_authority_not_granted",
            ],
            "next_action": "receive governed ref submissions before value binding",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request",
            "runtime_boundary": "required_explicit_decision_value_refs_requested_not_collected",
            "request_projection_only": True,
            **dict(_FALSE_FIELDS),
        },
    }
    _scan_private_or_secret_payload(envelope, path="envelope")
    return envelope


def _ref_request(source_ledger_id: str, ref_name: str, source_statuses: Sequence[Any]) -> dict[str, Any]:
    matching_statuses = [status for status in source_statuses if isinstance(status, Mapping) and status.get("ref_name") == ref_name]
    if len(matching_statuses) != 1:
        raise PersonalAssistantInvariantError(f"{ref_name} must have exactly one missing status before request")
    status = matching_statuses[0]
    _assert_required_ref_status_missing(status, ref_name)
    request_id = _require_pattern(
        f"pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request_item_{ref_name}",
        "required_ref_request_id",
        _REQUEST_ITEM_ID_PATTERN,
    )
    return {
        "required_ref_request_id": request_id,
        "ref_name": ref_name,
        "source_required_ref_status_id": _require_non_empty_text(status.get("required_ref_status_id"), "required_ref_status_id"),
        "source_explicit_decision_value_ref_status_ledger_id": source_ledger_id,
        "request_status": "requested_not_collected",
        "request_required": True,
        "missing": True,
        "present": False,
        "bound": False,
        "validated": False,
        "collected": False,
        "accepted": False,
        "stored": False,
        "grants_authority": False,
        "grants_verifier_execution": False,
        "operator_value_record_created": False,
        "verifier_execution_allowed": False,
        "authority_granted": False,
        "requested_evidence_uri": (
            "proof://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-execution-decision-value-record-value-explicit-decision-value-ref-request/"
            f"{ref_name}"
        ),
        "blocking_reason": f"{ref_name}_requested_not_collected",
    }


def _request_receipt(*, receipt_id: str, timestamp: str) -> dict[str, Any]:
    return {
        "receipt_id": receipt_id,
        "request_id": "pa_request_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request",
        "skill_id": "operator.reapproval.explicit_decision_ref_request",
        "mode": "blocked",
        "risk_level": "P4",
        "inputs_used": [
            "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger",
            "explicit_decision_value_ref_request_policy",
        ],
        "connectors_used": [],
        "decision": "blocked",
        "approval_required": True,
        "approval_ref": "",
        "actions_taken": [
            "explicit_decision_value_ref_request_created",
            "required_ref_requests_projected",
        ],
        "actions_not_taken": [
            "required_value_refs_not_collected",
            "required_value_refs_not_bound",
            "operator_decision_value_not_collected",
            "operator_identity_not_bound",
            "operator_signature_not_bound",
            "operator_reapproval_decision_receipt_not_bound",
            "operator_value_record_not_created",
            "verifier_execution_not_allowed",
            "external_message_not_sent",
            "connector_state_not_mutated",
            "system_of_record_not_written",
            "memory_not_written",
        ],
        "redactions": [
            "operator_decision_value_not_serialized",
            "operator_identity_not_serialized",
            "operator_signature_not_serialized",
            "operator_reapproval_decision_receipt_not_serialized",
            "private_connector_payload_not_serialized",
        ],
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": "no_connector_payload",
            "body_projection": "none",
        },
        "timestamp": timestamp,
        "evidence_refs": [
            "proof://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-execution-decision-value-record-value-explicit-decision-value-ref-request/foundation"
        ],
        "memory_observation_refs": [],
        "replay_refs": [
            "replay://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-execution-decision-value-record-value-explicit-decision-value-ref-request/foundation"
        ],
        "outcome": "AwaitingEvidence",
        "metadata": {
            "foundation_only": True,
            "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request_is_execution": False,
            "request_projection_only": True,
            "required_value_refs_requested": True,
            "required_value_refs_collected": False,
            **dict(_FALSE_FIELDS),
            "external_write_allowed": False,
        },
    }


def _summary(ref_requests: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "required_ref_request_count": len(ref_requests),
        "required_ref_requested_count": sum(1 for request in ref_requests if request.get("request_status") == "requested_not_collected"),
        "required_ref_collected_count": sum(1 for request in ref_requests if request.get("collected") is True),
        "required_ref_present_count": sum(1 for request in ref_requests if request.get("present") is True),
        "required_ref_bound_count": sum(1 for request in ref_requests if request.get("bound") is True),
        "required_ref_accepted_count": sum(1 for request in ref_requests if request.get("accepted") is True),
        "required_ref_stored_count": sum(1 for request in ref_requests if request.get("stored") is True),
        "operator_value_record_creation_count": sum(1 for request in ref_requests if request.get("operator_value_record_created") is True),
        "verifier_execution_allowed_count": sum(1 for request in ref_requests if request.get("verifier_execution_allowed") is True),
        "authority_grant_count": sum(1 for request in ref_requests if request.get("authority_granted") is True),
    }


def _assert_value_ref_status_ledger_boundary(source_envelope: Mapping[str, Any]) -> None:
    effect_boundary = _require_mapping(source_envelope.get("effect_boundary"), "effect_boundary")
    for field_name in (
        "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger_allowed",
        "explicit_decision_value_ref_preflight_ref_binding_allowed",
        "explicit_decision_value_ref_status_projection_allowed",
        "required_value_refs_declared",
        "required_value_refs_absent",
        "operator_decision_required",
        "operator_decision_value_required",
        "record_contract_ready",
        "verifier_ref_only",
    ):
        if effect_boundary.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"explicit decision value-ref status ledger effect_boundary.{field_name} must be true")
    for field_name in (
        "explicit_decision_value_ref_status_ledger_satisfied",
        "explicit_decision_value_ref_preflight_satisfied",
        "explicit_decision_value_refs_present",
        "explicit_operator_decision_value_bound",
        "operator_value_record_created",
        "operator_decision_value_present",
        "operator_decision_value_collected",
        "verifier_execution_allowed",
        "authority_granted",
        "live_connector_execution_allowed",
        "connector_mutation_allowed",
        "memory_write_allowed",
        "deployment_mutation_allowed",
        "nested_mind_live_activation_allowed",
        "public_readiness_claim_allowed",
    ):
        if effect_boundary.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"explicit decision value-ref status ledger effect_boundary.{field_name} must be false")
    if source_envelope.get("explicit_decision_value_ref_status_ledger_state") != "required_explicit_decision_value_refs_missing_unbound":
        raise PersonalAssistantInvariantError("explicit decision value-ref status ledger must remain missing unbound")
    if source_envelope.get("decision") != "blocked" or source_envelope.get("outcome") != "AwaitingEvidence":
        raise PersonalAssistantInvariantError("explicit decision value-ref status ledger must remain blocked AwaitingEvidence")

    source_statuses = _require_sequence(source_envelope.get("required_ref_statuses"), "required_ref_statuses")
    status_names = tuple(status.get("ref_name") for status in source_statuses if isinstance(status, Mapping))
    if status_names != _REQUIRED_VALUE_REFS:
        raise PersonalAssistantInvariantError("explicit decision value-ref status ledger must expose canonical required refs")
    for status in source_statuses:
        if not isinstance(status, Mapping):
            raise PersonalAssistantInvariantError("explicit decision value-ref status entry must be a mapping")
        _assert_required_ref_status_missing(status, _require_non_empty_text(status.get("ref_name"), "ref_name"))


def _assert_required_ref_status_missing(status: Mapping[str, Any], ref_name: str) -> None:
    expected = {
        "required": True,
        "status": "missing_unbound",
        "missing": True,
        "present": False,
        "bound": False,
        "validated": False,
        "grants_authority": False,
        "grants_verifier_execution": False,
        "operator_value_record_created": False,
        "verifier_execution_allowed": False,
        "authority_granted": False,
    }
    for field_name, expected_value in expected.items():
        if status.get(field_name) != expected_value:
            raise PersonalAssistantInvariantError(f"{ref_name} status.{field_name} must be {str(expected_value).lower()}")


def _require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PersonalAssistantInvariantError(f"{field_name} must be a mapping")
    return value


def _require_sequence(value: Any, field_name: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise PersonalAssistantInvariantError(f"{field_name} must be a sequence")
    return value


def _require_non_empty_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PersonalAssistantInvariantError(f"{field_name} must be a non-empty string")
    return value.strip()


def _require_pattern(value: str, field_name: str, pattern: re.Pattern[str]) -> str:
    text = _require_non_empty_text(value, field_name)
    if not pattern.fullmatch(text):
        raise PersonalAssistantInvariantError(f"{field_name} is not a governed identifier")
    return text


def _scan_private_or_secret_payload(value: Any, *, path: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            if key_text in _RAW_PRIVATE_FIELD_NAMES and key_text not in _ALLOWED_POLICY_FIELD_NAMES:
                raise PersonalAssistantInvariantError(f"{child_path} must not serialize raw private payload")
            _scan_private_or_secret_payload(child, path=child_path)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            _scan_private_or_secret_payload(child, path=f"{path}[{index}]")
        return
    if isinstance(value, str):
        for pattern in _SECRET_VALUE_PATTERNS:
            if pattern.search(value):
                raise PersonalAssistantInvariantError(f"{path} secret-like value must not be serialized")

"""Purpose: verifier execution explicit decision value-ref submitted-ref intake.
Governance scope: no-effect recording of submitted ref identifiers after the
explicit decision value-ref request, without accepting, binding, storing,
admitting, or executing any value.
Dependencies: personal-assistant explicit decision value-ref request runtime
and contracts.
Invariants:
  - Submitted refs are identifiers only, not raw operator values.
  - Submitted refs are not evidence acceptance, value binding, value storage,
    verifier execution, or authority.
  - No connector payload, operator identity payload, signature payload,
    decision receipt payload, verifier payload, or secret is serialized.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request import (
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request,
)


DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_SUBMITTED_REF_INTAKE_ID = (
    "pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake_foundation_001"
)
DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_SUBMITTED_REF_INTAKE_GENERATED_AT = (
    "2026-06-14T02:10:00+00:00"
)

_INTAKE_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake_[a-z0-9][a-z0-9_:-]*$"
)
_SUBMITTED_REF_RECORD_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_record_[a-z0-9][a-z0-9_:-]*$"
)
_REQUIRED_VALUE_REFS = (
    "operator_decision_value_ref",
    "operator_identity_ref",
    "operator_signature_ref",
    "operator_reapproval_decision_receipt_ref",
)
_FALSE_FIELDS = {
    "explicit_decision_value_ref_submitted_ref_intake_satisfied": False,
    "explicit_decision_value_ref_request_satisfied": False,
    "explicit_decision_value_refs_accepted": False,
    "explicit_decision_value_refs_bound": False,
    "explicit_decision_value_refs_validated": False,
    "explicit_decision_value_refs_stored": False,
    "explicit_operator_decision_value_bound": False,
    "operator_value_record_created": False,
    "operator_value_record_admitted": False,
    "operator_decision_value_stored": False,
    "operator_decision_value_present": False,
    "operator_decision_value_collected": False,
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
    "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake_allowed": True,
    "explicit_decision_value_ref_request_ref_binding_allowed": True,
    "explicit_decision_value_ref_submitted_ref_recording_allowed": True,
    "required_value_refs_declared": True,
    "required_value_refs_requested": True,
    "required_value_refs_submitted": True,
    "submitted_ref_only": True,
    "operator_decision_required": True,
    "operator_decision_value_required": True,
    "record_contract_ready": True,
    "verifier_ref_only": True,
    **_FALSE_FIELDS,
}
_PRIVATE_PAYLOAD_POLICY = {
    "raw_private_payload_serialized": False,
    "secret_values_serialized": False,
    "explicit_decision_value_ref_request_projection": "request_metadata_only",
    "explicit_decision_value_ref_submitted_ref_projection": "ref_identifier_only",
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
    "submitted_ref_payload",
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


def build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake(
    *,
    generated_at: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_SUBMITTED_REF_INTAKE_GENERATED_AT,
    explicit_decision_value_ref_submitted_ref_intake_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_SUBMITTED_REF_INTAKE_ID,
) -> dict[str, Any]:
    """Build deterministic no-effect explicit decision value-ref submitted-ref intake."""

    return build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake_envelope(
        generated_at=generated_at,
        explicit_decision_value_ref_submitted_ref_intake_id=explicit_decision_value_ref_submitted_ref_intake_id,
        operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request=(
            build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request()
        ),
    )


def build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake_envelope(
    *,
    generated_at: str,
    operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request: Mapping[str, Any],
    explicit_decision_value_ref_submitted_ref_intake_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_SUBMITTED_REF_INTAKE_ID,
) -> dict[str, Any]:
    """Build blocked submitted-ref intake from explicit decision value-ref request."""

    timestamp = _require_non_empty_text(generated_at, "generated_at")
    intake_id = _require_pattern(explicit_decision_value_ref_submitted_ref_intake_id, "explicit_decision_value_ref_submitted_ref_intake_id", _INTAKE_ID_PATTERN)
    source_envelope = _require_mapping(
        operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request,
        "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request",
    )
    _scan_private_or_secret_payload(source_envelope, path="operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request")
    _assert_value_ref_request_boundary(source_envelope)

    source_request_id = _require_non_empty_text(source_envelope.get("explicit_decision_value_ref_request_id"), "explicit_decision_value_ref_request_id")
    source_requests = _require_sequence(source_envelope.get("required_ref_requests"), "required_ref_requests")
    submitted_ref_records = [_submitted_ref_record(source_request_id, ref_name, source_requests) for ref_name in _REQUIRED_VALUE_REFS]
    receipt = _intake_receipt(
        receipt_id="pa_receipt_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake_foundation_001",
        timestamp=timestamp,
    )
    envelope = {
        "explicit_decision_value_ref_submitted_ref_intake_id": intake_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request",
        "source_explicit_decision_value_ref_request_id": source_request_id,
        "explicit_decision_value_ref_submitted_ref_intake_state": "submitted_refs_recorded_not_accepted",
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "submitted_ref_record_count": len(submitted_ref_records),
        "submitted_ref_record_ids": [record["submitted_ref_record_id"] for record in submitted_ref_records],
        "source_required_ref_request_ids": [record["source_required_ref_request_id"] for record in submitted_ref_records],
        "submitted_ref_uris": [record["submitted_ref_uri"] for record in submitted_ref_records],
        "submitted_ref_records": submitted_ref_records,
        "receipt": receipt,
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "summary": _summary(submitted_ref_records),
        "assurance": {
            "assurance_id": "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake_no_effect_assurance",
            "outcome": "AwaitingEvidence",
            "foundation_only": True,
            "submitted_ref_intake_only": True,
            "required_value_refs_requested": True,
            "required_value_refs_submitted": True,
            "submitted_ref_only": True,
            "explicit_decision_value_refs_accepted": False,
            "explicit_decision_value_refs_bound": False,
            "operator_decision_value_present": False,
            "operator_value_record_created": False,
            "verifier_execution_allowed": False,
            "authority_granted": False,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "blocking_reasons": [
                "submitted_refs_not_accepted",
                "submitted_refs_not_verified",
                "submitted_refs_not_bound",
                "operator_value_record_not_created",
                "verifier_execution_not_authorized",
                "execution_authority_not_granted",
            ],
            "next_action": "verify submitted refs before any value binding",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake",
            "runtime_boundary": "submitted_refs_recorded_not_accepted",
            "submitted_ref_intake_only": True,
            **dict(_FALSE_FIELDS),
        },
    }
    _scan_private_or_secret_payload(envelope, path="envelope")
    return envelope


def _submitted_ref_record(source_request_id: str, ref_name: str, source_requests: Sequence[Any]) -> dict[str, Any]:
    matching_requests = [request for request in source_requests if isinstance(request, Mapping) and request.get("ref_name") == ref_name]
    if len(matching_requests) != 1:
        raise PersonalAssistantInvariantError(f"{ref_name} must have exactly one requested ref before submitted-ref intake")
    request = matching_requests[0]
    _assert_required_ref_request_open(request, ref_name)
    record_id = _require_pattern(
        f"pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_record_{ref_name}",
        "submitted_ref_record_id",
        _SUBMITTED_REF_RECORD_ID_PATTERN,
    )
    submitted_ref_uri = (
        "evidence://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-execution-decision-value-record-value-explicit-decision-value-ref-submitted/"
        f"{ref_name}"
    )
    return {
        "submitted_ref_record_id": record_id,
        "ref_name": ref_name,
        "source_required_ref_request_id": _require_non_empty_text(request.get("required_ref_request_id"), "required_ref_request_id"),
        "source_explicit_decision_value_ref_request_id": source_request_id,
        "source_requested_evidence_uri": _require_non_empty_text(request.get("requested_evidence_uri"), "requested_evidence_uri"),
        "submitted_ref_uri": submitted_ref_uri,
        "submitted_ref_status": "submitted_not_accepted",
        "submitted_ref_recorded": True,
        "submitted_ref_only": True,
        "raw_ref_payload_present": False,
        "raw_operator_value_present": False,
        "present": True,
        "collected": False,
        "accepted": False,
        "bound": False,
        "validated": False,
        "stored": False,
        "grants_authority": False,
        "grants_verifier_execution": False,
        "operator_value_record_created": False,
        "verifier_execution_allowed": False,
        "authority_granted": False,
        "blocking_reason": f"{ref_name}_submitted_not_accepted",
    }


def _intake_receipt(*, receipt_id: str, timestamp: str) -> dict[str, Any]:
    return {
        "receipt_id": receipt_id,
        "request_id": "pa_request_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake",
        "skill_id": "operator.reapproval.explicit_decision_ref_submitted_ref_intake",
        "mode": "blocked",
        "risk_level": "P4",
        "inputs_used": [
            "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request",
            "explicit_decision_value_ref_submitted_ref_intake_policy",
        ],
        "connectors_used": [],
        "decision": "blocked",
        "approval_required": True,
        "approval_ref": "",
        "actions_taken": [
            "explicit_decision_value_ref_submitted_ref_intake_created",
            "submitted_ref_identifiers_recorded",
        ],
        "actions_not_taken": [
            "raw_operator_values_not_collected",
            "submitted_refs_not_accepted",
            "submitted_refs_not_bound",
            "operator_decision_value_not_stored",
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
            "proof://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-execution-decision-value-record-value-explicit-decision-value-ref-submitted-ref-intake/foundation"
        ],
        "memory_observation_refs": [],
        "replay_refs": [
            "replay://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-execution-decision-value-record-value-explicit-decision-value-ref-submitted-ref-intake/foundation"
        ],
        "outcome": "AwaitingEvidence",
        "metadata": {
            "foundation_only": True,
            "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake_is_execution": False,
            "submitted_ref_intake_only": True,
            "submitted_ref_only": True,
            "required_value_refs_submitted": True,
            "explicit_decision_value_refs_accepted": False,
            **dict(_FALSE_FIELDS),
            "external_write_allowed": False,
        },
    }


def _summary(submitted_ref_records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "submitted_ref_record_count": len(submitted_ref_records),
        "submitted_ref_recorded_count": sum(1 for record in submitted_ref_records if record.get("submitted_ref_recorded") is True),
        "submitted_ref_only_count": sum(1 for record in submitted_ref_records if record.get("submitted_ref_only") is True),
        "accepted_ref_count": sum(1 for record in submitted_ref_records if record.get("accepted") is True),
        "bound_ref_count": sum(1 for record in submitted_ref_records if record.get("bound") is True),
        "validated_ref_count": sum(1 for record in submitted_ref_records if record.get("validated") is True),
        "stored_ref_count": sum(1 for record in submitted_ref_records if record.get("stored") is True),
        "raw_ref_payload_count": sum(1 for record in submitted_ref_records if record.get("raw_ref_payload_present") is True),
        "raw_operator_value_count": sum(1 for record in submitted_ref_records if record.get("raw_operator_value_present") is True),
        "operator_value_record_creation_count": sum(1 for record in submitted_ref_records if record.get("operator_value_record_created") is True),
        "verifier_execution_allowed_count": sum(1 for record in submitted_ref_records if record.get("verifier_execution_allowed") is True),
        "authority_grant_count": sum(1 for record in submitted_ref_records if record.get("authority_granted") is True),
    }


def _assert_value_ref_request_boundary(source_envelope: Mapping[str, Any]) -> None:
    effect_boundary = _require_mapping(source_envelope.get("effect_boundary"), "effect_boundary")
    for field_name in (
        "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request_allowed",
        "explicit_decision_value_ref_status_ledger_ref_binding_allowed",
        "explicit_decision_value_ref_request_projection_allowed",
        "required_value_refs_declared",
        "required_value_refs_requested",
        "required_value_refs_absent",
        "operator_decision_required",
        "operator_decision_value_required",
        "record_contract_ready",
        "verifier_ref_only",
    ):
        if effect_boundary.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"explicit decision value-ref request effect_boundary.{field_name} must be true")
    for field_name in (
        "explicit_decision_value_ref_request_satisfied",
        "explicit_decision_value_refs_collected",
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
            raise PersonalAssistantInvariantError(f"explicit decision value-ref request effect_boundary.{field_name} must be false")
    if source_envelope.get("explicit_decision_value_ref_request_state") != "required_explicit_decision_value_refs_requested_not_collected":
        raise PersonalAssistantInvariantError("explicit decision value-ref request must remain requested not collected")
    if source_envelope.get("decision") != "blocked" or source_envelope.get("outcome") != "AwaitingEvidence":
        raise PersonalAssistantInvariantError("explicit decision value-ref request must remain blocked AwaitingEvidence")

    source_requests = _require_sequence(source_envelope.get("required_ref_requests"), "required_ref_requests")
    request_names = tuple(request.get("ref_name") for request in source_requests if isinstance(request, Mapping))
    if request_names != _REQUIRED_VALUE_REFS:
        raise PersonalAssistantInvariantError("explicit decision value-ref request must expose canonical required refs")
    for request in source_requests:
        if not isinstance(request, Mapping):
            raise PersonalAssistantInvariantError("explicit decision value-ref request entry must be a mapping")
        _assert_required_ref_request_open(request, _require_non_empty_text(request.get("ref_name"), "ref_name"))


def _assert_required_ref_request_open(request: Mapping[str, Any], ref_name: str) -> None:
    expected = {
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
    }
    for field_name, expected_value in expected.items():
        if request.get(field_name) != expected_value:
            raise PersonalAssistantInvariantError(f"{ref_name} request.{field_name} must be {str(expected_value).lower()}")


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

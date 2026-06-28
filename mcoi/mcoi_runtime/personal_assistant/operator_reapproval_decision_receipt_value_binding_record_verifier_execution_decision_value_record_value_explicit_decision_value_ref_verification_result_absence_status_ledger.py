"""Purpose: verifier execution explicit decision value-ref result absence status ledger.
Governance scope: no-effect compact ledger over absent verification results,
without receiving, accepting, binding, storing, admitting, or executing values.
Dependencies: personal-assistant explicit decision value-ref verification
result absence runtime and contracts.
Invariants:
  - Verification-result absence is summarized as status only.
  - Absence status never becomes verification, acceptance, binding, storage,
    verifier execution, or authority.
  - No connector payload, operator value, verifier result payload, or secret is
    serialized.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence import (
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence,
)


DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_VERIFICATION_RESULT_ABSENCE_STATUS_LEDGER_ID = (
    "pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger_foundation_001"
)
DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_VERIFICATION_RESULT_ABSENCE_STATUS_LEDGER_GENERATED_AT = (
    "2026-06-14T02:30:00+00:00"
)

_LEDGER_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger_[a-z0-9][a-z0-9_:-]*$"
)
_STATUS_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_[a-z0-9][a-z0-9_:-]*$"
)
_REQUIRED_VALUE_REFS = (
    "operator_decision_value_ref",
    "operator_identity_ref",
    "operator_signature_ref",
    "operator_reapproval_decision_receipt_ref",
)
_FALSE_FIELDS = {
    "explicit_decision_value_ref_verification_result_absence_status_ledger_satisfied": False,
    "explicit_decision_value_ref_verification_result_absence_satisfied": False,
    "explicit_decision_value_ref_verification_result_request_satisfied": False,
    "explicit_decision_value_refs_verified": False,
    "explicit_decision_value_refs_accepted": False,
    "explicit_decision_value_refs_bound": False,
    "explicit_decision_value_refs_validated": False,
    "explicit_decision_value_refs_stored": False,
    "verification_result_present": False,
    "verification_result_accepted": False,
    "verification_result_bound": False,
    "verification_result_stored": False,
    "operator_value_record_created": False,
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
    "authority_granted": False,
    "execution_worker_admission_allowed": False,
    "dispatch_allowed": False,
    "live_connector_execution_allowed": False,
    "connector_mutation_allowed": False,
    "system_of_record_write_allowed": False,
    "memory_write_allowed": False,
    "deployment_mutation_allowed": False,
    "nested_mind_live_activation_allowed": False,
    "public_readiness_claim_allowed": False,
}
_EFFECT_BOUNDARY = {
    "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger_allowed": True,
    "explicit_decision_value_ref_verification_result_absence_ref_binding_allowed": True,
    "explicit_decision_value_ref_verification_result_absence_status_projection_allowed": True,
    "required_value_refs_submitted": True,
    "submitted_ref_only": True,
    "verification_preflight_checked": True,
    "verification_result_requested": True,
    "verification_result_absence_recorded": True,
    "verification_result_absence_status_ledgered": True,
    "operator_decision_required": True,
    "operator_decision_value_required": True,
    "record_contract_ready": True,
    "verifier_ref_only": True,
    **_FALSE_FIELDS,
}
_PRIVATE_PAYLOAD_POLICY = {
    "raw_private_payload_serialized": False,
    "secret_values_serialized": False,
    "explicit_decision_value_ref_submitted_ref_projection": "ref_identifier_only",
    "explicit_decision_value_ref_verification_projection": "preflight_status_only",
    "explicit_decision_value_ref_verification_result_projection": "absence_status_only",
    "explicit_decision_value_ref_verification_result_absence_status_projection": "absence_ledger_status_only",
    "operator_decision_value_projection": "absent",
    "operator_value_record_projection": "absent",
    "verifier_result_payload_projection": "absent",
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
    "raw_operator_value",
    "raw_result_payload",
    "raw_verification_result_payload",
    "verification_result_payload",
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


def build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger(
    *,
    generated_at: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_VERIFICATION_RESULT_ABSENCE_STATUS_LEDGER_GENERATED_AT,
    explicit_decision_value_ref_verification_result_absence_status_ledger_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_VERIFICATION_RESULT_ABSENCE_STATUS_LEDGER_ID,
) -> dict[str, Any]:
    """Build deterministic no-effect verification result absence status ledger."""

    return build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger_envelope(
        generated_at=generated_at,
        explicit_decision_value_ref_verification_result_absence_status_ledger_id=explicit_decision_value_ref_verification_result_absence_status_ledger_id,
        operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence=(
            build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence()
        ),
    )


def build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger_envelope(
    *,
    generated_at: str,
    operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence: Mapping[str, Any],
    explicit_decision_value_ref_verification_result_absence_status_ledger_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_VERIFICATION_RESULT_ABSENCE_STATUS_LEDGER_ID,
) -> dict[str, Any]:
    """Build blocked absence status ledger from result-absence evidence."""

    timestamp = _require_non_empty_text(generated_at, "generated_at")
    ledger_id = _require_pattern(explicit_decision_value_ref_verification_result_absence_status_ledger_id, "explicit_decision_value_ref_verification_result_absence_status_ledger_id", _LEDGER_ID_PATTERN)
    source_envelope = _require_mapping(
        operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence,
        "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence",
    )
    _scan_private_or_secret_payload(source_envelope, path="operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence")
    _assert_absence_boundary(source_envelope)

    source_absence_id = _require_non_empty_text(source_envelope.get("explicit_decision_value_ref_verification_result_absence_id"), "explicit_decision_value_ref_verification_result_absence_id")
    source_records = _require_sequence(source_envelope.get("absence_records"), "absence_records")
    statuses = [_absence_status(source_absence_id, ref_name, source_records) for ref_name in _REQUIRED_VALUE_REFS]
    receipt = _ledger_receipt(
        receipt_id="pa_receipt_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger_foundation_001",
        timestamp=timestamp,
    )
    envelope = {
        "explicit_decision_value_ref_verification_result_absence_status_ledger_id": ledger_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence",
        "source_explicit_decision_value_ref_verification_result_absence_id": source_absence_id,
        "explicit_decision_value_ref_verification_result_absence_status_ledger_state": "verification_result_absence_status_ledgered",
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "absence_status_count": len(statuses),
        "absence_status_ids": [status["absence_status_id"] for status in statuses],
        "source_absence_record_ids": [status["source_absence_record_id"] for status in statuses],
        "submitted_ref_uris": [status["submitted_ref_uri"] for status in statuses],
        "absence_statuses": statuses,
        "receipt": receipt,
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "summary": _summary(statuses),
        "assurance": {
            "assurance_id": "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger_no_effect_assurance",
            "outcome": "AwaitingEvidence",
            "foundation_only": True,
            "status_ledger_only": True,
            "verification_result_absence_recorded": True,
            "verification_result_absence_status_ledgered": True,
            "verification_result_present": False,
            "explicit_decision_value_refs_verified": False,
            "explicit_decision_value_refs_accepted": False,
            "explicit_decision_value_refs_bound": False,
            "explicit_decision_value_refs_stored": False,
            "operator_decision_value_present": False,
            "operator_value_record_created": False,
            "verifier_execution_allowed": False,
            "authority_granted": False,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "blocking_reasons": [f"{ref_name}_verification_result_absent" for ref_name in _REQUIRED_VALUE_REFS],
            "next_action": "collect governed verification results before acceptance can be considered",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger",
            "runtime_boundary": "verification_result_absence_status_ledgered",
            "verification_result_absence_status_ledger_only": True,
            **dict(_FALSE_FIELDS),
        },
    }
    _scan_private_or_secret_payload(envelope, path="envelope")
    return envelope


def _absence_status(source_absence_id: str, ref_name: str, source_records: Sequence[Any]) -> dict[str, Any]:
    matching_records = [record for record in source_records if isinstance(record, Mapping) and record.get("ref_name") == ref_name]
    if len(matching_records) != 1:
        raise PersonalAssistantInvariantError(f"{ref_name} must have exactly one absence record before status ledger")
    source_record = matching_records[0]
    _assert_absence_record_open(source_record, ref_name)
    status_id = _require_pattern(
        f"pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_{ref_name}",
        "absence_status_id",
        _STATUS_ID_PATTERN,
    )
    return {
        "absence_status_id": status_id,
        "ref_name": ref_name,
        "source_absence_record_id": _require_non_empty_text(source_record.get("absence_record_id"), "absence_record_id"),
        "source_explicit_decision_value_ref_verification_result_absence_id": source_absence_id,
        "submitted_ref_uri": _require_non_empty_text(source_record.get("submitted_ref_uri"), "submitted_ref_uri"),
        "status": "verification_result_absent_after_request",
        "verification_result_requested": True,
        "verification_result_absence_recorded": True,
        "verification_result_absence_status_ledgered": True,
        "verification_result_present": False,
        "submitted_ref_only": True,
        "raw_result_payload_present": False,
        "raw_operator_value_present": False,
        "verified": False,
        "accepted": False,
        "bound": False,
        "validated": False,
        "stored": False,
        "grants_authority": False,
        "grants_verifier_execution": False,
        "operator_value_record_created": False,
        "verifier_execution_allowed": False,
        "authority_granted": False,
        "blocking_reason": f"{ref_name}_verification_result_absent",
    }


def _ledger_receipt(*, receipt_id: str, timestamp: str) -> dict[str, Any]:
    return {
        "receipt_id": receipt_id,
        "request_id": "pa_request_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger",
        "skill_id": "operator.reapproval.explicit_decision_ref_verification_result_absence_status_ledger",
        "mode": "blocked",
        "risk_level": "P4",
        "inputs_used": [
            "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence",
            "explicit_decision_value_ref_verification_result_absence_status_ledger_policy",
        ],
        "connectors_used": [],
        "decision": "blocked",
        "approval_required": True,
        "approval_ref": "",
        "actions_taken": [
            "explicit_decision_value_ref_verification_result_absence_status_ledger_recorded",
            "verification_result_absence_status_summarized",
        ],
        "actions_not_taken": [
            "raw_verification_results_not_collected",
            "raw_operator_values_not_collected",
            "submitted_refs_not_verified",
            "submitted_refs_not_accepted",
            "submitted_refs_not_bound",
            "operator_decision_value_not_stored",
            "operator_value_record_not_created",
            "verifier_execution_not_allowed",
            "external_message_not_sent",
            "connector_state_not_mutated",
            "system_of_record_not_written",
            "memory_not_written",
        ],
        "redactions": [
            "verification_result_payload_absent",
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
            "proof://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-execution-decision-value-record-value-explicit-decision-value-ref-verification-result-absence-status-ledger/foundation"
        ],
        "memory_observation_refs": [],
        "replay_refs": [
            "replay://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-execution-decision-value-record-value-explicit-decision-value-ref-verification-result-absence-status-ledger/foundation"
        ],
        "outcome": "AwaitingEvidence",
        "metadata": {
            "foundation_only": True,
            "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger_is_execution": False,
            "verification_result_absence_status_ledger_only": True,
            "submitted_ref_only": True,
            "verification_result_requested": True,
            "verification_result_absence_recorded": True,
            "verification_result_absence_status_ledgered": True,
            "verification_result_present": False,
            "explicit_decision_value_refs_verified": False,
            "explicit_decision_value_refs_accepted": False,
            **dict(_FALSE_FIELDS),
            "external_write_allowed": False,
        },
    }


def _summary(statuses: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "absence_status_count": len(statuses),
        "verification_result_requested_count": sum(1 for status in statuses if status.get("verification_result_requested") is True),
        "verification_result_absence_recorded_count": sum(1 for status in statuses if status.get("verification_result_absence_recorded") is True),
        "verification_result_absence_status_ledgered_count": sum(1 for status in statuses if status.get("verification_result_absence_status_ledgered") is True),
        "verification_result_present_count": sum(1 for status in statuses if status.get("verification_result_present") is True),
        "submitted_ref_only_count": sum(1 for status in statuses if status.get("submitted_ref_only") is True),
        "verified_ref_count": sum(1 for status in statuses if status.get("verified") is True),
        "accepted_ref_count": sum(1 for status in statuses if status.get("accepted") is True),
        "bound_ref_count": sum(1 for status in statuses if status.get("bound") is True),
        "validated_ref_count": sum(1 for status in statuses if status.get("validated") is True),
        "stored_ref_count": sum(1 for status in statuses if status.get("stored") is True),
        "raw_result_payload_count": sum(1 for status in statuses if status.get("raw_result_payload_present") is True),
        "raw_operator_value_count": sum(1 for status in statuses if status.get("raw_operator_value_present") is True),
        "operator_value_record_creation_count": sum(1 for status in statuses if status.get("operator_value_record_created") is True),
        "verifier_execution_allowed_count": sum(1 for status in statuses if status.get("verifier_execution_allowed") is True),
        "authority_grant_count": sum(1 for status in statuses if status.get("authority_granted") is True),
    }


def _assert_absence_boundary(source_envelope: Mapping[str, Any]) -> None:
    effect_boundary = _require_mapping(source_envelope.get("effect_boundary"), "effect_boundary")
    for field_name in (
        "required_value_refs_submitted",
        "submitted_ref_only",
        "verification_preflight_checked",
        "verification_result_requested",
        "verification_result_absence_recorded",
        "operator_decision_required",
        "operator_decision_value_required",
        "record_contract_ready",
        "verifier_ref_only",
    ):
        if effect_boundary.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"explicit decision value-ref verification result absence effect_boundary.{field_name} must be true")
    for field_name in (
        "verification_result_present",
        "explicit_decision_value_refs_verified",
        "explicit_decision_value_refs_accepted",
        "explicit_decision_value_refs_bound",
        "explicit_decision_value_refs_validated",
        "explicit_decision_value_refs_stored",
        "operator_value_record_created",
        "operator_decision_value_present",
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
            raise PersonalAssistantInvariantError(f"explicit decision value-ref verification result absence effect_boundary.{field_name} must be false")
    if source_envelope.get("explicit_decision_value_ref_verification_result_absence_state") != "verification_results_absent_after_request":
        raise PersonalAssistantInvariantError("explicit decision value-ref verification result absence must remain absent after request")
    if source_envelope.get("decision") != "blocked" or source_envelope.get("outcome") != "AwaitingEvidence":
        raise PersonalAssistantInvariantError("explicit decision value-ref verification result absence must remain blocked AwaitingEvidence")

    source_records = _require_sequence(source_envelope.get("absence_records"), "absence_records")
    record_names = tuple(record.get("ref_name") for record in source_records if isinstance(record, Mapping))
    if record_names != _REQUIRED_VALUE_REFS:
        raise PersonalAssistantInvariantError("explicit decision value-ref verification result absence must expose canonical required refs")
    for record in source_records:
        if not isinstance(record, Mapping):
            raise PersonalAssistantInvariantError("explicit decision value-ref verification result absence record must be a mapping")
        _assert_absence_record_open(record, _require_non_empty_text(record.get("ref_name"), "ref_name"))


def _assert_absence_record_open(record: Mapping[str, Any], ref_name: str) -> None:
    expected = {
        "absence_status": "absent_after_request",
        "verification_result_requested": True,
        "verification_result_absence_recorded": True,
        "verification_result_present": False,
        "submitted_ref_only": True,
        "raw_result_payload_present": False,
        "raw_operator_value_present": False,
        "verified": False,
        "accepted": False,
        "bound": False,
        "validated": False,
        "stored": False,
        "grants_authority": False,
        "grants_verifier_execution": False,
        "operator_value_record_created": False,
        "verifier_execution_allowed": False,
        "authority_granted": False,
    }
    for field_name, expected_value in expected.items():
        if record.get(field_name) != expected_value:
            raise PersonalAssistantInvariantError(f"{ref_name} absence_record.{field_name} must be {str(expected_value).lower()}")


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

"""Purpose: explicit decision value-ref absence status closure packet.
Governance scope: no-effect packet over absent verification result status,
without collecting values, accepting refs, storing records, or granting
verifier execution authority.
Dependencies: personal-assistant absence status ledger runtime and contracts.
Invariants:
  - Closure packet is an AwaitingEvidence summary, not terminal closure.
  - Absent verification results remain absent and non-authoritative.
  - No connector payload, operator value, verifier result payload, or secret is
    serialized.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger import (
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger,
)


DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_VERIFICATION_RESULT_ABSENCE_STATUS_CLOSURE_PACKET_ID = (
    "pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_closure_packet_foundation_001"
)
DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_VERIFICATION_RESULT_ABSENCE_STATUS_CLOSURE_PACKET_GENERATED_AT = (
    "2026-06-14T02:45:00+00:00"
)

_PACKET_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_closure_packet_[a-z0-9][a-z0-9_:-]*$"
)
_REQUIRED_VALUE_REFS = (
    "operator_decision_value_ref",
    "operator_identity_ref",
    "operator_signature_ref",
    "operator_reapproval_decision_receipt_ref",
)
_FALSE_FIELDS = {
    "closure_satisfied": False,
    "terminal_closure_claimed": False,
    "explicit_decision_value_ref_verification_result_absence_status_closure_packet_satisfied": False,
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
_PRIVATE_PAYLOAD_POLICY = {
    "raw_private_payload_serialized": False,
    "secret_values_serialized": False,
    "closure_packet_projection": "absence_status_summary_only",
    "explicit_decision_value_ref_verification_result_projection": "absence_status_only",
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


def build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_closure_packet(
    *,
    generated_at: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_VERIFICATION_RESULT_ABSENCE_STATUS_CLOSURE_PACKET_GENERATED_AT,
    explicit_decision_value_ref_verification_result_absence_status_closure_packet_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_VERIFICATION_RESULT_ABSENCE_STATUS_CLOSURE_PACKET_ID,
) -> dict[str, Any]:
    """Build deterministic no-effect absence status closure packet."""

    return build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_closure_packet_envelope(
        generated_at=generated_at,
        explicit_decision_value_ref_verification_result_absence_status_closure_packet_id=explicit_decision_value_ref_verification_result_absence_status_closure_packet_id,
        operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger=(
            build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger()
        ),
    )


def build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_closure_packet_envelope(
    *,
    generated_at: str,
    operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger: Mapping[str, Any],
    explicit_decision_value_ref_verification_result_absence_status_closure_packet_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_VERIFICATION_RESULT_ABSENCE_STATUS_CLOSURE_PACKET_ID,
) -> dict[str, Any]:
    """Build blocked closure packet from absence status ledger evidence."""

    timestamp = _require_non_empty_text(generated_at, "generated_at")
    packet_id = _require_pattern(explicit_decision_value_ref_verification_result_absence_status_closure_packet_id, "explicit_decision_value_ref_verification_result_absence_status_closure_packet_id", _PACKET_ID_PATTERN)
    source_ledger = _require_mapping(
        operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger,
        "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger",
    )
    _scan_private_or_secret_payload(source_ledger, path="source_ledger")
    _assert_absence_status_ledger_boundary(source_ledger)

    source_ledger_id = _require_non_empty_text(source_ledger.get("explicit_decision_value_ref_verification_result_absence_status_ledger_id"), "explicit_decision_value_ref_verification_result_absence_status_ledger_id")
    source_absence_id = _require_non_empty_text(source_ledger.get("source_explicit_decision_value_ref_verification_result_absence_id"), "source_explicit_decision_value_ref_verification_result_absence_id")
    statuses = _require_sequence(source_ledger.get("absence_statuses"), "absence_statuses")
    obligations = [_evidence_obligation(status) for status in statuses]
    closure_state = {
        "can_close_verifier_execution": False,
        "can_close_value_binding": False,
        "can_close_authority_grant": False,
        "can_close_terminal_readiness": False,
        "missing_verification_result_count": len(obligations),
        "pending_evidence_obligation_count": len(obligations),
        "blocking_reason_count": len(obligations),
    }
    receipt = _closure_receipt(
        receipt_id="pa_receipt_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_closure_packet_foundation_001",
        timestamp=timestamp,
    )
    envelope = {
        "explicit_decision_value_ref_verification_result_absence_status_closure_packet_id": packet_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger",
        "source_explicit_decision_value_ref_verification_result_absence_status_ledger_id": source_ledger_id,
        "source_explicit_decision_value_ref_verification_result_absence_id": source_absence_id,
        "explicit_decision_value_ref_verification_result_absence_status_closure_packet_state": "closure_packet_blocked_awaiting_verification_results",
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "closure_state": closure_state,
        "blocking_reasons": [obligation["blocking_reason"] for obligation in obligations],
        "pending_evidence_obligations": obligations,
        "receipt": receipt,
        "effect_boundary": {
            "absence_status_closure_packet_allowed": True,
            "absence_status_ledger_projection_allowed": True,
            "pending_evidence_obligation_projection_allowed": True,
            "required_value_refs_submitted": True,
            "submitted_ref_only": True,
            "verification_preflight_checked": True,
            "verification_result_requested": True,
            "verification_result_absence_recorded": True,
            "verification_result_absence_status_ledgered": True,
            "closure_packet_recorded": True,
            "operator_decision_required": True,
            "operator_decision_value_required": True,
            "record_contract_ready": True,
            "verifier_ref_only": True,
            **dict(_FALSE_FIELDS),
        },
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "summary": _summary(obligations, closure_state),
        "assurance": {
            "assurance_id": "personal_assistant_explicit_decision_value_ref_verification_result_absence_status_closure_packet_no_effect_assurance",
            "outcome": "AwaitingEvidence",
            "foundation_only": True,
            "closure_packet_only": True,
            "terminal_closure_claimed": False,
            "verification_result_absence_recorded": True,
            "verification_result_absence_status_ledgered": True,
            "verification_result_present": False,
            "explicit_decision_value_refs_verified": False,
            "explicit_decision_value_refs_accepted": False,
            "authority_granted": False,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "next_action": "collect governed verification results before closure can be considered",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_closure_packet",
            "runtime_boundary": "closure_packet_blocked_awaiting_verification_results",
            "closure_packet_only": True,
            "terminal_closure_claimed": False,
            **dict(_FALSE_FIELDS),
        },
    }
    _scan_private_or_secret_payload(envelope, path="envelope")
    return envelope


def _evidence_obligation(status: Mapping[str, Any]) -> dict[str, Any]:
    ref_name = _require_non_empty_text(status.get("ref_name"), "ref_name")
    if ref_name not in _REQUIRED_VALUE_REFS:
        raise PersonalAssistantInvariantError(f"{ref_name} is not a canonical required value ref")
    expected = {
        "verification_result_requested": True,
        "verification_result_absence_recorded": True,
        "verification_result_absence_status_ledgered": True,
        "verification_result_present": False,
        "submitted_ref_only": True,
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
        if status.get(field_name) is not expected_value:
            raise PersonalAssistantInvariantError(f"{ref_name} absence status {field_name} must be {str(expected_value).lower()}")
    return {
        "obligation_id": f"pa_explicit_decision_value_ref_verification_result_obligation_{ref_name}",
        "ref_name": ref_name,
        "submitted_ref_uri": _require_non_empty_text(status.get("submitted_ref_uri"), "submitted_ref_uri"),
        "source_absence_status_id": _require_non_empty_text(status.get("absence_status_id"), "absence_status_id"),
        "required_evidence": "governed_verification_result",
        "current_status": "verification_result_absent",
        "blocking_reason": f"{ref_name}_verification_result_absent",
        "must_remain_ref_only_until_verified": True,
        "raw_result_payload_present": False,
        "raw_operator_value_present": False,
        "verification_result_present": False,
        "verified": False,
        "accepted": False,
        "bound": False,
        "stored": False,
        "grants_authority": False,
        "grants_verifier_execution": False,
    }


def _closure_receipt(*, receipt_id: str, timestamp: str) -> dict[str, Any]:
    return {
        "receipt_id": receipt_id,
        "request_id": "pa_request_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_closure_packet",
        "skill_id": "operator.reapproval.explicit_decision_ref_verification_result_absence_status_closure_packet",
        "mode": "blocked",
        "risk_level": "P4",
        "inputs_used": [
            "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger",
            "explicit_decision_value_ref_verification_result_absence_status_closure_packet_policy",
        ],
        "connectors_used": [],
        "decision": "blocked",
        "approval_required": True,
        "approval_ref": "",
        "actions_taken": [
            "explicit_decision_value_ref_verification_result_absence_status_closure_packet_recorded",
            "pending_verification_result_obligations_projected",
        ],
        "actions_not_taken": [
            "terminal_closure_not_claimed",
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
            "proof://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-execution-decision-value-record-value-explicit-decision-value-ref-verification-result-absence-status-closure-packet/foundation"
        ],
        "memory_observation_refs": [],
        "replay_refs": [
            "replay://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-execution-decision-value-record-value-explicit-decision-value-ref-verification-result-absence-status-closure-packet/foundation"
        ],
        "outcome": "AwaitingEvidence",
        "metadata": {
            "foundation_only": True,
            "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_closure_packet_is_execution": False,
            "closure_packet_only": True,
            "terminal_closure_claimed": False,
            "submitted_ref_only": True,
            "verification_result_requested": True,
            "verification_result_absence_recorded": True,
            "verification_result_absence_status_ledgered": True,
            "verification_result_present": False,
            "external_write_allowed": False,
            **dict(_FALSE_FIELDS),
        },
    }


def _summary(obligations: Sequence[Mapping[str, Any]], closure_state: Mapping[str, Any]) -> dict[str, int]:
    return {
        "pending_evidence_obligation_count": len(obligations),
        "missing_verification_result_count": int(closure_state.get("missing_verification_result_count", 0)),
        "blocking_reason_count": int(closure_state.get("blocking_reason_count", 0)),
        "verification_result_present_count": sum(1 for obligation in obligations if obligation.get("verification_result_present") is True),
        "submitted_ref_only_count": sum(1 for obligation in obligations if obligation.get("must_remain_ref_only_until_verified") is True),
        "verified_ref_count": sum(1 for obligation in obligations if obligation.get("verified") is True),
        "accepted_ref_count": sum(1 for obligation in obligations if obligation.get("accepted") is True),
        "bound_ref_count": sum(1 for obligation in obligations if obligation.get("bound") is True),
        "stored_ref_count": sum(1 for obligation in obligations if obligation.get("stored") is True),
        "raw_result_payload_count": sum(1 for obligation in obligations if obligation.get("raw_result_payload_present") is True),
        "raw_operator_value_count": sum(1 for obligation in obligations if obligation.get("raw_operator_value_present") is True),
        "authority_grant_count": sum(1 for obligation in obligations if obligation.get("grants_authority") is True),
        "verifier_execution_grant_count": sum(1 for obligation in obligations if obligation.get("grants_verifier_execution") is True),
    }


def _assert_absence_status_ledger_boundary(source_ledger: Mapping[str, Any]) -> None:
    if source_ledger.get("explicit_decision_value_ref_verification_result_absence_status_ledger_state") != "verification_result_absence_status_ledgered":
        raise PersonalAssistantInvariantError("explicit decision value-ref verification result absence status ledger must be ledgered")
    if source_ledger.get("decision") != "blocked" or source_ledger.get("outcome") != "AwaitingEvidence":
        raise PersonalAssistantInvariantError("explicit decision value-ref verification result absence status ledger must remain blocked AwaitingEvidence")
    effect_boundary = _require_mapping(source_ledger.get("effect_boundary"), "effect_boundary")
    for field_name in (
        "required_value_refs_submitted",
        "submitted_ref_only",
        "verification_preflight_checked",
        "verification_result_requested",
        "verification_result_absence_recorded",
        "verification_result_absence_status_ledgered",
        "operator_decision_required",
        "operator_decision_value_required",
        "record_contract_ready",
        "verifier_ref_only",
    ):
        if effect_boundary.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"absence status ledger effect_boundary.{field_name} must be true")
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
            raise PersonalAssistantInvariantError(f"absence status ledger effect_boundary.{field_name} must be false")
    statuses = _require_sequence(source_ledger.get("absence_statuses"), "absence_statuses")
    names = tuple(status.get("ref_name") for status in statuses if isinstance(status, Mapping))
    if names != _REQUIRED_VALUE_REFS:
        raise PersonalAssistantInvariantError("absence status ledger must expose canonical required refs")


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

"""Purpose: review explicit decision value-ref absence closure packet status.
Governance scope: no-effect review over a blocked AwaitingEvidence closure
packet without accepting refs, executing verifiers, writing memory, or granting
authority.
Dependencies: personal-assistant absence closure packet runtime and contracts.
Invariants:
  - Review is a projection, not terminal closure.
  - All absent verification result obligations remain pending.
  - No connector payload, operator value, verifier result payload, or secret is
    serialized.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .ref_absence_closure_packet import (
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_closure_packet,
)


DEFAULT_PERSONAL_ASSISTANT_REF_ABSENCE_CLOSURE_REVIEW_ID = "pa_ref_absence_closure_review_foundation_001"
DEFAULT_PERSONAL_ASSISTANT_REF_ABSENCE_CLOSURE_REVIEW_GENERATED_AT = "2026-06-14T03:00:00+00:00"

_REVIEW_ID_PATTERN = re.compile(r"^pa_ref_absence_closure_review_[a-z0-9][a-z0-9_:-]*$")
_REQUIRED_VALUE_REFS = (
    "operator_decision_value_ref",
    "operator_identity_ref",
    "operator_signature_ref",
    "operator_reapproval_decision_receipt_ref",
)
_FALSE_FIELDS = {
    "review_satisfied": False,
    "closure_satisfied": False,
    "terminal_closure_claimed": False,
    "source_closure_packet_satisfied": False,
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
    "operator_decision_value_present": False,
    "operator_decision_value_collected": False,
    "operator_decision_value_stored": False,
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
    "review_projection": "closure_packet_summary_only",
    "source_closure_packet_projection": "blocked_status_only",
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


def build_default_personal_assistant_ref_absence_closure_review(
    *,
    generated_at: str = DEFAULT_PERSONAL_ASSISTANT_REF_ABSENCE_CLOSURE_REVIEW_GENERATED_AT,
    review_id: str = DEFAULT_PERSONAL_ASSISTANT_REF_ABSENCE_CLOSURE_REVIEW_ID,
) -> dict[str, Any]:
    """Build deterministic no-effect closure review."""

    return build_personal_assistant_ref_absence_closure_review_envelope(
        generated_at=generated_at,
        review_id=review_id,
        source_closure_packet=build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_closure_packet(),
    )


def build_personal_assistant_ref_absence_closure_review_envelope(
    *,
    generated_at: str,
    source_closure_packet: Mapping[str, Any],
    review_id: str = DEFAULT_PERSONAL_ASSISTANT_REF_ABSENCE_CLOSURE_REVIEW_ID,
) -> dict[str, Any]:
    """Build blocked review envelope from a source closure packet."""

    timestamp = _require_non_empty_text(generated_at, "generated_at")
    governed_review_id = _require_pattern(review_id, "review_id", _REVIEW_ID_PATTERN)
    source = _require_mapping(source_closure_packet, "source_closure_packet")
    _scan_private_or_secret_payload(source, path="source_closure_packet")
    _assert_source_closure_packet_boundary(source)
    review_items = [_review_item(obligation) for obligation in _require_sequence(source.get("pending_evidence_obligations"), "pending_evidence_obligations")]
    review_state = {
        "can_close_review": False,
        "can_close_source_packet": False,
        "can_close_verifier_execution": False,
        "can_close_authority_grant": False,
        "can_close_terminal_readiness": False,
        "reviewed_obligation_count": len(review_items),
        "pending_evidence_obligation_count": len(review_items),
        "missing_verification_result_count": len(review_items),
        "blocking_reason_count": len(review_items),
    }
    envelope = {
        "ref_absence_closure_review_id": governed_review_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "personal_assistant_ref_absence_closure_packet",
        "source_ref_absence_closure_packet_id": _require_non_empty_text(source.get("explicit_decision_value_ref_verification_result_absence_status_closure_packet_id"), "source_closure_packet_id"),
        "ref_absence_closure_review_state": "closure_review_blocked_awaiting_verification_results",
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "review_state": review_state,
        "review_items": review_items,
        "blocking_reasons": [item["blocking_reason"] for item in review_items],
        "receipt": _review_receipt(timestamp=timestamp),
        "effect_boundary": {
            "closure_review_allowed": True,
            "source_closure_packet_projection_allowed": True,
            "pending_evidence_obligation_review_allowed": True,
            "review_recorded": True,
            "required_value_refs_submitted": True,
            "submitted_ref_only": True,
            "verification_result_requested": True,
            "verification_result_absence_recorded": True,
            "verification_result_absence_status_ledgered": True,
            "source_closure_packet_recorded": True,
            "operator_decision_required": True,
            "operator_decision_value_required": True,
            "verifier_ref_only": True,
            **dict(_FALSE_FIELDS),
        },
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "summary": _summary(review_items, review_state),
        "assurance": {
            "assurance_id": "personal_assistant_ref_absence_closure_review_no_effect_assurance",
            "outcome": "AwaitingEvidence",
            "foundation_only": True,
            "review_only": True,
            "terminal_closure_claimed": False,
            "source_closure_packet_reviewed": True,
            "verification_result_absence_recorded": True,
            "verification_result_present": False,
            "explicit_decision_value_refs_verified": False,
            "explicit_decision_value_refs_accepted": False,
            "authority_granted": False,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "next_action": "collect governed verification results before review can close",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "personal_assistant_ref_absence_closure_review",
            "runtime_boundary": "closure_review_blocked_awaiting_verification_results",
            "review_only": True,
            "terminal_closure_claimed": False,
            **dict(_FALSE_FIELDS),
        },
    }
    _scan_private_or_secret_payload(envelope, path="envelope")
    return envelope


def _review_item(obligation: Mapping[str, Any]) -> dict[str, Any]:
    ref_name = _require_non_empty_text(obligation.get("ref_name"), "ref_name")
    if ref_name not in _REQUIRED_VALUE_REFS:
        raise PersonalAssistantInvariantError(f"{ref_name} is not a canonical required value ref")
    expected = {
        "required_evidence": "governed_verification_result",
        "current_status": "verification_result_absent",
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
    for field_name, expected_value in expected.items():
        if obligation.get(field_name) != expected_value:
            raise PersonalAssistantInvariantError(f"{ref_name} obligation {field_name} must be {str(expected_value).lower()}")
    return {
        "review_item_id": f"pa_ref_absence_closure_review_item_{ref_name}",
        "ref_name": ref_name,
        "source_obligation_id": _require_non_empty_text(obligation.get("obligation_id"), "obligation_id"),
        "submitted_ref_uri": _require_non_empty_text(obligation.get("submitted_ref_uri"), "submitted_ref_uri"),
        "review_result": "blocked_missing_governed_verification_result",
        "blocking_reason": _require_non_empty_text(obligation.get("blocking_reason"), "blocking_reason"),
        "required_next_evidence": "governed_verification_result",
        "reviewed": True,
        "pending": True,
        "verification_result_present": False,
        "verified": False,
        "accepted": False,
        "bound": False,
        "stored": False,
        "grants_authority": False,
        "grants_verifier_execution": False,
    }


def _review_receipt(*, timestamp: str) -> dict[str, Any]:
    return {
        "receipt_id": "pa_receipt_ref_absence_closure_review_foundation_001",
        "request_id": "pa_request_ref_absence_closure_review",
        "skill_id": "operator.reapproval.explicit_decision_ref_verification_result_absence_closure_review",
        "mode": "blocked",
        "risk_level": "P4",
        "inputs_used": ["personal_assistant_ref_absence_closure_packet", "personal_assistant_ref_absence_closure_review_policy"],
        "connectors_used": [],
        "decision": "blocked",
        "approval_required": True,
        "approval_ref": "",
        "actions_taken": ["source_closure_packet_reviewed", "pending_verification_result_obligations_reviewed", "closure_review_recorded"],
        "actions_not_taken": [
            "terminal_closure_not_claimed",
            "source_closure_packet_not_accepted_as_satisfied",
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
            "deployment_not_mutated",
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
        "evidence_refs": ["proof://personal-assistant/ref-absence-closure-review/foundation"],
        "memory_observation_refs": [],
        "replay_refs": ["replay://personal-assistant/ref-absence-closure-review/foundation"],
        "outcome": "AwaitingEvidence",
        "metadata": {
            "foundation_only": True,
            "ref_absence_closure_review_is_execution": False,
            "review_only": True,
            "terminal_closure_claimed": False,
            "submitted_ref_only": True,
            "verification_result_requested": True,
            "verification_result_absence_recorded": True,
            "verification_result_present": False,
            "external_write_allowed": False,
            **dict(_FALSE_FIELDS),
        },
    }


def _summary(review_items: Sequence[Mapping[str, Any]], review_state: Mapping[str, Any]) -> dict[str, int]:
    return {
        "reviewed_obligation_count": int(review_state.get("reviewed_obligation_count", 0)),
        "pending_evidence_obligation_count": int(review_state.get("pending_evidence_obligation_count", 0)),
        "missing_verification_result_count": int(review_state.get("missing_verification_result_count", 0)),
        "blocking_reason_count": int(review_state.get("blocking_reason_count", 0)),
        "verification_result_present_count": sum(1 for item in review_items if item.get("verification_result_present") is True),
        "verified_ref_count": sum(1 for item in review_items if item.get("verified") is True),
        "accepted_ref_count": sum(1 for item in review_items if item.get("accepted") is True),
        "bound_ref_count": sum(1 for item in review_items if item.get("bound") is True),
        "stored_ref_count": sum(1 for item in review_items if item.get("stored") is True),
        "authority_grant_count": sum(1 for item in review_items if item.get("grants_authority") is True),
        "verifier_execution_grant_count": sum(1 for item in review_items if item.get("grants_verifier_execution") is True),
    }


def _assert_source_closure_packet_boundary(source: Mapping[str, Any]) -> None:
    if source.get("explicit_decision_value_ref_verification_result_absence_status_closure_packet_state") != "closure_packet_blocked_awaiting_verification_results":
        raise PersonalAssistantInvariantError("source closure packet must remain blocked awaiting verification results")
    if source.get("decision") != "blocked" or source.get("outcome") != "AwaitingEvidence":
        raise PersonalAssistantInvariantError("source closure packet must remain blocked AwaitingEvidence")
    closure_state = _require_mapping(source.get("closure_state"), "closure_state")
    for field_name in ("can_close_verifier_execution", "can_close_value_binding", "can_close_authority_grant", "can_close_terminal_readiness"):
        if closure_state.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"source closure_state.{field_name} must be false")
    for field_name in ("missing_verification_result_count", "pending_evidence_obligation_count", "blocking_reason_count"):
        if closure_state.get(field_name) != len(_REQUIRED_VALUE_REFS):
            raise PersonalAssistantInvariantError(f"source closure_state.{field_name} must be four")
    effect_boundary = _require_mapping(source.get("effect_boundary"), "effect_boundary")
    for field_name in (
        "verification_result_present",
        "explicit_decision_value_refs_verified",
        "explicit_decision_value_refs_accepted",
        "explicit_decision_value_refs_bound",
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
        "terminal_closure_claimed",
    ):
        if effect_boundary.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"source effect_boundary.{field_name} must be false")
    names = tuple(obligation.get("ref_name") for obligation in _require_sequence(source.get("pending_evidence_obligations"), "pending_evidence_obligations"))
    if names != _REQUIRED_VALUE_REFS:
        raise PersonalAssistantInvariantError("source closure packet must expose canonical required refs")


def _require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PersonalAssistantInvariantError(f"{field_name} must be a mapping")
    return value


def _require_sequence(value: Any, field_name: str) -> Sequence[Mapping[str, Any]]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise PersonalAssistantInvariantError(f"{field_name} must be a sequence")
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise PersonalAssistantInvariantError(f"{field_name}[{index}] must be a mapping")
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

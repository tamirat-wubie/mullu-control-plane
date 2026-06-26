"""Purpose: operator reapproval value-binding record evidence requests.
Governance scope: request-only operator evidence slots, admission-preflight
refs, private-payload redaction, and no-execution boundaries.
Dependencies: personal-assistant operator reapproval decision receipt value
binding record admission preflight runtime and contracts.
Invariants:
  - Evidence requests are not evidence submissions, accepted evidence, or
    value-binding records.
  - No raw operator value, identity, signature, receipt payload, connector
    payload, or secret is collected, inferred, accepted, or serialized.
  - Execution-worker admission, dispatch, live connector execution, connector
    mutation, external sends, memory writes, system-of-record writes,
    deployment mutation, and readiness claims remain false.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .operator_reapproval_decision_receipt_value_binding_record_admission_preflight import (
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_admission_preflight,
)


DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_EVIDENCE_REQUEST_SET_ID = (
    "pa_operator_reapproval_decision_receipt_value_binding_record_evidence_request_foundation_001"
)
DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_EVIDENCE_REQUEST_GENERATED_AT = (
    "2026-06-14T00:22:00+00:00"
)

_EVIDENCE_REQUEST_SET_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_evidence_request_[a-z0-9][a-z0-9_:-]*$"
)
_EVIDENCE_REQUEST_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_evidence_request_item_[a-z0-9][a-z0-9_:-]*$"
)
_ALLOWED_DECISION_VALUES = ("approved", "rejected", "revised", "expired")
_EVIDENCE_SLOT_KINDS = (
    "operator_decision_value_ref",
    "operator_identity_ref",
    "operator_signature_ref",
    "operator_reapproval_decision_receipt_ref",
)
_EFFECT_BOUNDARY = {
    "operator_reapproval_decision_receipt_value_binding_record_evidence_request_allowed": True,
    "value_binding_record_admission_preflight_ref_binding_allowed": True,
    "operator_evidence_slot_request_allowed": True,
    "operator_input_request_allowed": True,
    "operator_submitted_value_ref_required": True,
    "operator_identity_ref_required": True,
    "operator_signature_ref_required": True,
    "decision_receipt_ref_required": True,
    "evidence_request_issued": True,
    "evidence_request_is_submission": False,
    "evidence_request_is_acceptance": False,
    "evidence_submitted": False,
    "evidence_accepted": False,
    "evidence_rejected": False,
    "operator_value_collected": False,
    "explicit_operator_value_present": False,
    "operator_value_bound": False,
    "operator_identity_ref_bound": False,
    "operator_signature_ref_bound": False,
    "decision_receipt_ref_bound": False,
    "accepted_value_present": False,
    "binding_record_candidate_accepted": False,
    "binding_record_created": False,
    "binding_record_admitted": False,
    "admission_approved": False,
    "authority_granted": False,
    "execution_worker_admission_allowed": False,
    "dispatch_allowed": False,
    "dispatch_lease_active": False,
    "live_connector_receipt_present": False,
    "live_connector_execution_allowed": False,
    "external_send_allowed": False,
    "calendar_write_allowed": False,
    "task_write_allowed": False,
    "memory_write_allowed": False,
    "connector_mutation_allowed": False,
    "system_of_record_write_allowed": False,
    "deployment_mutation_allowed": False,
    "nested_mind_live_activation_allowed": False,
    "public_readiness_claim_allowed": False,
}
_PRIVATE_PAYLOAD_POLICY = {
    "raw_private_payload_serialized": False,
    "secret_values_serialized": False,
    "value_binding_record_admission_preflight_projection": "ref_only",
    "operator_decision_value_projection": "ref_request_only",
    "operator_identity_ref_projection": "ref_request_only",
    "operator_signature_ref_projection": "ref_request_only",
    "decision_receipt_projection": "ref_request_only",
    "evidence_submission_projection": "absent",
}
_RAW_PRIVATE_FIELD_NAMES = frozenset(
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
_ALLOWED_POLICY_FIELD_NAMES = frozenset(
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


def build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request(
    *,
    generated_at: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_EVIDENCE_REQUEST_GENERATED_AT,
    value_binding_record_evidence_request_set_id: str = (
        DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_EVIDENCE_REQUEST_SET_ID
    ),
) -> dict[str, Any]:
    """Build deterministic request-only value-binding record evidence requests."""

    return build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_envelope(
        generated_at=generated_at,
        value_binding_record_evidence_request_set_id=value_binding_record_evidence_request_set_id,
        operator_reapproval_decision_receipt_value_binding_record_admission_preflight=(
            build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_admission_preflight()
        ),
    )


def build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_envelope(
    *,
    generated_at: str,
    operator_reapproval_decision_receipt_value_binding_record_admission_preflight: Mapping[str, Any],
    value_binding_record_evidence_request_set_id: str = (
        DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_EVIDENCE_REQUEST_SET_ID
    ),
) -> dict[str, Any]:
    """Build operator evidence request slots from blocked admission preflights."""

    timestamp = _require_non_empty_text(generated_at, "generated_at")
    envelope_id = _require_pattern(
        value_binding_record_evidence_request_set_id,
        "value_binding_record_evidence_request_set_id",
        _EVIDENCE_REQUEST_SET_ID_PATTERN,
    )
    source_envelope = _require_mapping(
        operator_reapproval_decision_receipt_value_binding_record_admission_preflight,
        "operator_reapproval_decision_receipt_value_binding_record_admission_preflight",
    )
    _scan_private_or_secret_payload(source_envelope, path="operator_reapproval_decision_receipt_value_binding_record_admission_preflight")
    _assert_admission_preflight_boundary(source_envelope)
    source_preflight_set_id = _require_non_empty_text(
        source_envelope.get("value_binding_record_admission_preflight_set_id"),
        "value_binding_record_admission_preflight_set_id",
    )

    request_slots: list[dict[str, Any]] = []
    evidence_request_ids: list[str] = []
    source_preflight_ids: list[str] = []
    receipt_ids: list[str] = []
    preflights = source_envelope.get("admission_preflights")
    if isinstance(preflights, (str, bytes)) or not isinstance(preflights, Sequence):
        raise PersonalAssistantInvariantError("operator reapproval value-binding record admission_preflights must be a sequence")
    for preflight in preflights:
        if not isinstance(preflight, Mapping):
            raise PersonalAssistantInvariantError("operator reapproval value-binding record admission preflight item must be a mapping")
        _assert_preflight_item_boundary(preflight)
        for slot_kind in _EVIDENCE_SLOT_KINDS:
            request_slot = _evidence_request_slot(source_preflight_set_id, preflight, slot_kind=slot_kind, timestamp=timestamp)
            if request_slot["evidence_request_id"] in evidence_request_ids:
                raise PersonalAssistantInvariantError(f"duplicate evidence_request_id {request_slot['evidence_request_id']}")
            evidence_request_ids.append(request_slot["evidence_request_id"])
            source_preflight_ids.append(request_slot["source_admission_preflight_id"])
            receipt_ids.append(request_slot["receipt"]["receipt_id"])
            request_slots.append(request_slot)
    if not request_slots:
        raise PersonalAssistantInvariantError("operator reapproval value-binding record evidence request requires at least one slot")

    envelope = {
        "value_binding_record_evidence_request_set_id": envelope_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "operator_reapproval_decision_receipt_value_binding_record_admission_preflight",
        "source_operator_reapproval_decision_receipt_value_binding_record_admission_preflight_set_id": source_preflight_set_id,
        "evidence_request_state": "requested_not_submitted",
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "evidence_request_count": len(request_slots),
        "evidence_request_ids": evidence_request_ids,
        "source_admission_preflight_ids": source_preflight_ids,
        "receipt_ids": receipt_ids,
        "evidence_requests": request_slots,
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "summary": _summary(request_slots),
        "assurance": {
            "assurance_id": "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_no_effect_assurance",
            "outcome": "AwaitingEvidence",
            "foundation_only": True,
            "request_only": True,
            "ready_for_evidence_submission": False,
            "ready_for_binding_record_admission": False,
            "ready_for_execution_worker_admission": False,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "checked_controls": [
                "admission_preflight_required",
                "admission_preflight_ref_bound",
                "operator_evidence_slots_requested",
                "request_only_no_submission",
                "no_raw_operator_value_storage",
                "no_execution_worker_admission",
                "no_dispatch",
                "no_live_connector_execution",
            ],
            "blocking_reasons": [
                "operator_evidence_not_submitted",
                "operator_evidence_not_accepted",
                "value_binding_record_not_created",
                "execution_authority_not_granted",
            ],
            "next_action": "submit separate governed evidence refs for each request slot without raw operator value serialization",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "operator_reapproval_decision_receipt_value_binding_record_evidence_request_ref_only",
            "runtime_boundary": "evidence_request_does_not_submit_accept_or_bind_operator_values",
            "request_only": True,
            "operator_value_collected": False,
            "explicit_operator_value_present": False,
            "operator_value_bound": False,
            "operator_identity_ref_bound": False,
            "operator_signature_ref_bound": False,
            "decision_receipt_ref_bound": False,
            "accepted_value_present": False,
            "binding_record_candidate_accepted": False,
            "binding_record_created": False,
            "binding_record_admitted": False,
            "admission_approved": False,
            "authority_granted": False,
            "execution_worker_admission_allowed": False,
            "dispatch_allowed": False,
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_send_allowed": False,
            "calendar_write_allowed": False,
            "task_write_allowed": False,
            "system_of_record_write_allowed": False,
            "deployment_mutation_allowed": False,
            "nested_mind_live_activation_allowed": False,
            "public_readiness_claim_allowed": False,
            "memory_write_allowed": False,
        },
    }
    _scan_private_or_secret_payload(envelope, path="envelope")
    return envelope


def _evidence_request_slot(
    source_preflight_set_id: str,
    preflight: Mapping[str, Any],
    *,
    slot_kind: str,
    timestamp: str,
) -> dict[str, Any]:
    source_preflight_id = _require_non_empty_text(preflight.get("admission_preflight_id"), "source_admission_preflight_id")
    approval_id = _require_non_empty_text(preflight.get("approval_id"), "approval_id")
    request_id = _require_non_empty_text(preflight.get("request_id"), "request_id")
    plan_id = _require_non_empty_text(preflight.get("plan_id"), "plan_id")
    skill_id = _require_non_empty_text(preflight.get("skill_id"), "skill_id")
    risk_level = _require_non_empty_text(preflight.get("risk_level"), "risk_level")
    suffix = approval_id.removeprefix("pa_approval_")
    request_id_value = _require_pattern(
        f"pa_operator_reapproval_decision_receipt_value_binding_record_evidence_request_item_{slot_kind}_{suffix}",
        "evidence_request_id",
        _EVIDENCE_REQUEST_ID_PATTERN,
    )
    return {
        "evidence_request_id": request_id_value,
        "evidence_kind": slot_kind,
        "source_admission_preflight_id": source_preflight_id,
        "approval_id": approval_id,
        "request_id": request_id,
        "plan_id": plan_id,
        "skill_id": skill_id,
        "risk_level": risk_level,
        "source_admission_preflight_ref": {
            "source_admission_preflight_set_id": source_preflight_set_id,
            "source_admission_preflight_id": source_preflight_id,
            "source_outcome": "GovernanceBlocked",
            "binding_record_created": False,
            "execution_worker_admission_allowed": False,
        },
        "request_contract": {
            "request_state": "requested",
            "proof_state": "Unknown",
            "required": True,
            "request_only": True,
            "ref_only": True,
            "raw_value_requested": False,
            "raw_payload_requested": False,
            "evidence_submission_required_later": True,
            "allowed_decision_values": list(_ALLOWED_DECISION_VALUES),
        },
        "submission_state": {
            "evidence_submitted": False,
            "evidence_accepted": False,
            "evidence_rejected": False,
            "submitted_evidence_refs": [],
            "accepted_evidence_refs": [],
            "rejected_evidence_refs": [],
            "requirement_satisfied": False,
            "authority_granted": False,
        },
        "blocked_actions": [
            "raw_operator_value_collection",
            "operator_evidence_submission",
            "operator_evidence_acceptance",
            "value_binding_record_creation",
            "value_binding_record_admission",
            "execution_worker_admission",
            "dispatch",
            "live_connector_execution",
            "connector_mutation",
            "external_send",
            "system_of_record_write",
            "memory_write",
        ],
        "receipt": _evidence_request_receipt(
            receipt_id=f"pa_receipt_operator_reapproval_decision_receipt_value_binding_record_evidence_request_{slot_kind}_{suffix}",
            request_id=request_id,
            skill_id=skill_id,
            risk_level=risk_level,
            approval_id=approval_id,
            slot_kind=slot_kind,
            timestamp=timestamp,
        ),
    }


def _evidence_request_receipt(
    *,
    receipt_id: str,
    request_id: str,
    skill_id: str,
    risk_level: str,
    approval_id: str,
    slot_kind: str,
    timestamp: str,
) -> dict[str, Any]:
    return {
        "receipt_id": receipt_id,
        "request_id": request_id,
        "skill_id": skill_id,
        "mode": "execute_with_approval",
        "risk_level": risk_level,
        "inputs_used": [
            "operator_reapproval_decision_receipt_value_binding_record_admission_preflight",
            "operator_reapproval_decision_receipt_value_binding_record_evidence_request_policy",
        ],
        "connectors_used": ["gmail"] if skill_id.startswith("email.") else [],
        "decision": "blocked",
        "approval_required": True,
        "approval_ref": approval_id,
        "actions_taken": [
            f"{slot_kind}_evidence_request_issued",
            "request_only_receipt_created",
        ],
        "actions_not_taken": [
            "raw_operator_decision_value_not_collected",
            "operator_identity_ref_not_collected",
            "operator_signature_ref_not_collected",
            "operator_reapproval_receipt_not_collected",
            "operator_evidence_not_submitted",
            "operator_evidence_not_accepted",
            "operator_decision_value_not_bound",
            "binding_record_candidate_not_accepted",
            "binding_record_not_created",
            "binding_record_not_admitted",
            "execution_worker_not_admitted",
            "dispatch_not_started",
            "live_connector_receipt_not_collected",
            "external_message_not_sent",
            "connector_state_not_mutated",
            "system_of_record_not_written",
            "memory_not_written",
        ],
        "redactions": [
            "operator_decision_value_absent",
            "operator_identity_ref_absent",
            "operator_signature_absent",
            "decision_receipt_absent",
            "private_connector_payload_not_serialized",
        ],
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": "ref_only",
            "body_projection": "none",
        },
        "timestamp": timestamp,
        "evidence_refs": [f"proof://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-evidence-request/{approval_id}/{slot_kind}"],
        "memory_observation_refs": [],
        "replay_refs": [f"replay://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-evidence-request/{approval_id}/{slot_kind}"],
        "outcome": "AwaitingEvidence",
        "metadata": {
            "foundation_only": True,
            "operator_reapproval_decision_receipt_value_binding_record_evidence_request_is_execution": False,
            "evidence_kind": slot_kind,
            "request_only": True,
            "raw_value_requested": False,
            "operator_value_collected": False,
            "explicit_operator_value_present": False,
            "operator_value_bound": False,
            "operator_identity_ref_bound": False,
            "operator_signature_ref_bound": False,
            "decision_receipt_ref_bound": False,
            "accepted_value_present": False,
            "binding_record_candidate_accepted": False,
            "binding_record_created": False,
            "binding_record_admitted": False,
            "admission_approved": False,
            "authority_granted": False,
            "execution_worker_admission_allowed": False,
            "dispatch_allowed": False,
            "dispatch_lease_active": False,
            "live_connector_receipt_present": False,
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_write_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
            "money_legal_public_action_allowed": False,
        },
    }


def _summary(request_slots: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    submission_states = [_require_mapping(slot.get("submission_state"), "submission_state") for slot in request_slots]
    request_contracts = [_require_mapping(slot.get("request_contract"), "request_contract") for slot in request_slots]
    return {
        "evidence_request_count": len(request_slots),
        "requested_slot_count": sum(1 for contract in request_contracts if contract.get("request_state") == "requested"),
        "operator_input_required_count": len(request_slots),
        "unknown_proof_state_count": sum(1 for contract in request_contracts if contract.get("proof_state") == "Unknown"),
        "submitted_evidence_count": sum(1 for state in submission_states if state.get("evidence_submitted") is True),
        "accepted_evidence_count": sum(1 for state in submission_states if state.get("evidence_accepted") is True),
        "rejected_evidence_count": sum(1 for state in submission_states if state.get("evidence_rejected") is True),
        "satisfied_requirement_count": sum(1 for state in submission_states if state.get("requirement_satisfied") is True),
        "authority_grant_count": sum(1 for state in submission_states if state.get("authority_granted") is True),
        "binding_record_creation_count": sum(1 for slot in request_slots if slot.get("binding_record_created") is True),
    }


def _assert_admission_preflight_boundary(source_envelope: Mapping[str, Any]) -> None:
    effect_boundary = _require_mapping(source_envelope.get("effect_boundary"), "effect_boundary")
    for field_name in (
        "operator_reapproval_decision_receipt_value_binding_record_admission_preflight_allowed",
        "value_binding_record_guard_ref_binding_allowed",
        "missing_operator_evidence_detection_allowed",
        "admission_decision_allowed",
        "operator_submitted_value_required",
        "operator_identity_ref_required",
        "operator_signature_ref_required",
        "decision_receipt_required",
    ):
        if effect_boundary.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"value binding record admission preflight effect_boundary.{field_name} must be true")
    for field_name in (
        "operator_value_collected",
        "explicit_operator_value_present",
        "operator_value_bound",
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
    ):
        if effect_boundary.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"value binding record admission preflight effect_boundary.{field_name} must be false")
    if _require_mapping(source_envelope.get("assurance"), "assurance").get("outcome") != "GovernanceBlocked":
        raise PersonalAssistantInvariantError("value binding record admission preflight assurance.outcome must be GovernanceBlocked")


def _assert_preflight_item_boundary(preflight: Mapping[str, Any]) -> None:
    missing_evidence = _require_mapping(preflight.get("missing_operator_evidence"), "missing_operator_evidence")
    if tuple(missing_evidence.get("allowed_decision_values", ())) != _ALLOWED_DECISION_VALUES:
        raise PersonalAssistantInvariantError("admission preflight allowed_decision_values must preserve policy")
    for field_name in (
        "operator_submitted_value_present",
        "operator_identity_ref_present",
        "operator_signature_ref_present",
        "decision_receipt_ref_present",
    ):
        if missing_evidence.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"admission preflight missing_operator_evidence.{field_name} must be false")
    admission_decision = _require_mapping(preflight.get("admission_decision"), "admission_decision")
    if admission_decision.get("decision") != "blocked" or admission_decision.get("outcome") != "GovernanceBlocked":
        raise PersonalAssistantInvariantError("admission preflight decision must remain blocked GovernanceBlocked")
    for field_name in (
        "operator_value_bound",
        "binding_record_created",
        "binding_record_admitted",
        "authority_granted",
        "execution_worker_admission_allowed",
        "dispatch_allowed",
    ):
        if admission_decision.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"admission preflight admission_decision.{field_name} must be false")


def _require_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PersonalAssistantInvariantError(f"{field_name} must be a mapping")
    return dict(value)


def _require_non_empty_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PersonalAssistantInvariantError(f"{field_name} must be a non-empty string")
    if any(pattern.search(value) for pattern in _SECRET_VALUE_PATTERNS):
        raise PersonalAssistantInvariantError(f"{field_name} must not contain secret-like values")
    return value


def _require_pattern(value: str, field_name: str, pattern: re.Pattern[str]) -> str:
    text = _require_non_empty_text(value, field_name)
    if not pattern.fullmatch(text):
        raise PersonalAssistantInvariantError(f"{field_name} has invalid governed identifier shape")
    return text


def _scan_private_or_secret_payload(payload: Any, *, path: str) -> None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            normalized_key = str(key).lower()
            if normalized_key not in _ALLOWED_POLICY_FIELD_NAMES and normalized_key in _RAW_PRIVATE_FIELD_NAMES:
                raise PersonalAssistantInvariantError(f"{path}.{key}: raw private or secret field is forbidden")
            _scan_private_or_secret_payload(value, path=f"{path}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _scan_private_or_secret_payload(value, path=f"{path}[{index}]")
    elif isinstance(payload, str) and any(pattern.search(payload) for pattern in _SECRET_VALUE_PATTERNS):
        raise PersonalAssistantInvariantError(f"{path}: secret-like value must not be serialized")

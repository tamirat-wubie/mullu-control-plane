"""Purpose: operator reapproval decision value-binding record admission preflight.
Governance scope: value-binding record guard refs, missing operator evidence,
admission denial, private-payload redaction, and no-execution boundaries.
Dependencies: personal-assistant operator reapproval decision receipt value
binding record guard runtime and contracts.
Invariants:
  - The preflight records why a value-binding record cannot be admitted yet.
  - No operator value, identity ref, signature, or decision receipt payload is
    collected, accepted, inferred, fabricated, or serialized.
  - Execution-worker admission, dispatch, live connector execution, connector
    mutation, external sends, memory writes, system-of-record writes,
    deployment mutation, and readiness claims remain false.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .operator_reapproval_decision_receipt_value_binding_record_guard import (
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_guard,
)


DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_ADMISSION_PREFLIGHT_SET_ID = (
    "pa_operator_reapproval_decision_receipt_value_binding_record_admission_preflight_foundation_001"
)
DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_ADMISSION_PREFLIGHT_GENERATED_AT = (
    "2026-06-14T00:21:00+00:00"
)

_PREFLIGHT_SET_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_admission_preflight_[a-z0-9][a-z0-9_:-]*$"
)
_PREFLIGHT_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_admission_preflight_item_[a-z0-9][a-z0-9_:-]*$"
)
_ALLOWED_DECISION_VALUES = ("approved", "rejected", "revised", "expired")
_EFFECT_BOUNDARY = {
    "operator_reapproval_decision_receipt_value_binding_record_admission_preflight_allowed": True,
    "value_binding_record_guard_ref_binding_allowed": True,
    "missing_operator_evidence_detection_allowed": True,
    "admission_decision_allowed": True,
    "operator_submitted_value_required": True,
    "operator_identity_ref_required": True,
    "operator_signature_ref_required": True,
    "decision_receipt_required": True,
    "operator_value_collected": False,
    "explicit_operator_value_present": False,
    "operator_value_bound": False,
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
    "value_binding_record_guard_projection": "ref_only",
    "candidate_record_projection": "requirements_only",
    "decision_value_projection": "absent",
    "operator_identity_ref_projection": "absent",
    "operator_signature_projection": "absent",
    "decision_receipt_projection": "absent",
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
        "operator_identity_ref",
        "operator_signature",
        "raw_decision_receipt",
    }
)
_ALLOWED_POLICY_FIELD_NAMES = frozenset(
    {
        "private_payload_policy",
        "raw_private_payload_serialized",
        "secret_values_serialized",
        "value_binding_record_guard_projection",
        "candidate_record_projection",
        "decision_value_projection",
        "operator_identity_ref_projection",
        "operator_signature_projection",
        "decision_receipt_projection",
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


def build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_admission_preflight(
    *,
    generated_at: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_ADMISSION_PREFLIGHT_GENERATED_AT,
    value_binding_record_admission_preflight_set_id: str = (
        DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_ADMISSION_PREFLIGHT_SET_ID
    ),
) -> dict[str, Any]:
    """Build deterministic no-effect value-binding record admission preflight."""

    return build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_admission_preflight_envelope(
        generated_at=generated_at,
        value_binding_record_admission_preflight_set_id=value_binding_record_admission_preflight_set_id,
        operator_reapproval_decision_receipt_value_binding_record_guard=(
            build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_guard()
        ),
    )


def build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_admission_preflight_envelope(
    *,
    generated_at: str,
    operator_reapproval_decision_receipt_value_binding_record_guard: Mapping[str, Any],
    value_binding_record_admission_preflight_set_id: str = (
        DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_ADMISSION_PREFLIGHT_SET_ID
    ),
) -> dict[str, Any]:
    """Build blocked admission preflights from value-binding record guard evidence."""

    timestamp = _require_non_empty_text(generated_at, "generated_at")
    envelope_id = _require_pattern(
        value_binding_record_admission_preflight_set_id,
        "value_binding_record_admission_preflight_set_id",
        _PREFLIGHT_SET_ID_PATTERN,
    )
    source_envelope = _require_mapping(
        operator_reapproval_decision_receipt_value_binding_record_guard,
        "operator_reapproval_decision_receipt_value_binding_record_guard",
    )
    _scan_private_or_secret_payload(source_envelope, path="operator_reapproval_decision_receipt_value_binding_record_guard")
    _assert_record_guard_boundary(source_envelope)
    source_guard_set_id = _require_non_empty_text(
        source_envelope.get("value_binding_record_guard_set_id"),
        "value_binding_record_guard_set_id",
    )

    preflights: list[dict[str, Any]] = []
    preflight_ids: list[str] = []
    source_guard_ids: list[str] = []
    receipt_ids: list[str] = []
    source_guards = source_envelope.get("record_guards")
    if isinstance(source_guards, (str, bytes)) or not isinstance(source_guards, Sequence):
        raise PersonalAssistantInvariantError("operator_reapproval_decision_receipt_value_binding_record_guard.record_guards must be a sequence")
    for source_guard in source_guards:
        if not isinstance(source_guard, Mapping):
            raise PersonalAssistantInvariantError("operator reapproval decision receipt value binding record guard item must be a mapping")
        preflight = _preflight_item(source_guard_set_id, source_guard, timestamp=timestamp)
        if preflight["admission_preflight_id"] in preflight_ids:
            raise PersonalAssistantInvariantError(f"duplicate admission_preflight_id {preflight['admission_preflight_id']}")
        preflight_ids.append(preflight["admission_preflight_id"])
        source_guard_ids.append(preflight["source_record_guard_id"])
        receipt_ids.append(preflight["receipt"]["receipt_id"])
        preflights.append(preflight)
    if not preflights:
        raise PersonalAssistantInvariantError("operator reapproval decision receipt value binding record admission preflight requires at least one record guard")

    envelope = {
        "value_binding_record_admission_preflight_set_id": envelope_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "operator_reapproval_decision_receipt_value_binding_record_guard",
        "source_operator_reapproval_decision_receipt_value_binding_record_guard_set_id": source_guard_set_id,
        "admission_preflight_count": len(preflights),
        "admission_preflight_ids": preflight_ids,
        "source_record_guard_ids": source_guard_ids,
        "receipt_ids": receipt_ids,
        "admission_preflights": preflights,
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "assurance": {
            "assurance_id": "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_admission_preflight_no_effect_assurance",
            "outcome": "GovernanceBlocked",
            "foundation_only": True,
            "ready_for_binding_record_admission": False,
            "ready_for_execution_worker_admission": False,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "checked_controls": [
                "value_binding_record_guard_required",
                "record_guard_ref_bound",
                "operator_value_absence_detected",
                "operator_identity_ref_absence_detected",
                "operator_signature_ref_absence_detected",
                "decision_receipt_absence_detected",
                "admission_denied",
                "no_execution_worker_admission",
                "no_dispatch",
                "no_live_connector_execution",
            ],
            "blocking_reasons": [
                "operator_submitted_decision_value_absent",
                "operator_identity_ref_absent",
                "operator_signature_ref_absent",
                "operator_reapproval_decision_receipt_absent",
            ],
            "next_action": "submit governed operator value, identity ref, signature ref, and decision receipt to a separate value-binding record path",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "operator_reapproval_decision_receipt_value_binding_record_admission_preflight_evidence_only",
            "runtime_boundary": "record_admission_preflight_blocks_missing_operator_evidence",
            "operator_value_collected": False,
            "explicit_operator_value_present": False,
            "operator_value_bound": False,
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


def _preflight_item(source_guard_set_id: str, source_guard: Mapping[str, Any], *, timestamp: str) -> dict[str, Any]:
    source_guard_id = _require_non_empty_text(source_guard.get("record_guard_id"), "source_record_guard_id")
    approval_id = _require_non_empty_text(source_guard.get("approval_id"), "approval_id")
    request_id = _require_non_empty_text(source_guard.get("request_id"), "request_id")
    plan_id = _require_non_empty_text(source_guard.get("plan_id"), "plan_id")
    skill_id = _require_non_empty_text(source_guard.get("skill_id"), "skill_id")
    risk_level = _require_non_empty_text(source_guard.get("risk_level"), "risk_level")
    candidate_requirements = _require_mapping(source_guard.get("record_candidate_requirements"), "record_candidate_requirements")
    execution_block = _require_mapping(source_guard.get("execution_admission_block"), "execution_admission_block")
    _assert_record_guard_item_boundary(source_guard_id, candidate_requirements, execution_block)
    suffix = approval_id.removeprefix("pa_approval_")
    preflight_id = _require_pattern(
        f"pa_operator_reapproval_decision_receipt_value_binding_record_admission_preflight_item_{suffix}",
        "admission_preflight_id",
        _PREFLIGHT_ID_PATTERN,
    )
    return {
        "admission_preflight_id": preflight_id,
        "source_record_guard_id": source_guard_id,
        "approval_id": approval_id,
        "request_id": request_id,
        "plan_id": plan_id,
        "skill_id": skill_id,
        "risk_level": risk_level,
        "value_binding_record_guard_ref": {
            "source_record_guard_set_id": source_guard_set_id,
            "source_record_guard_id": source_guard_id,
            "guard_outcome": "AwaitingEvidence",
            "binding_record_created": False,
            "execution_worker_admission_allowed": False,
        },
        "missing_operator_evidence": {
            "operator_submitted_value_present": False,
            "operator_identity_ref_present": False,
            "operator_signature_ref_present": False,
            "decision_receipt_ref_present": False,
            "allowed_decision_values": list(_ALLOWED_DECISION_VALUES),
            "required_next_evidence": "governed_operator_reapproval_decision_receipt_value_binding_record",
        },
        "admission_decision": {
            "decision": "blocked",
            "admission_state": "blocked_missing_governed_operator_value_binding_record_evidence",
            "outcome": "GovernanceBlocked",
            "operator_value_bound": False,
            "binding_record_created": False,
            "binding_record_admitted": False,
            "authority_granted": False,
            "execution_worker_admission_allowed": False,
            "dispatch_allowed": False,
        },
        "execution_admission_block": {
            "execution_worker_admission_state": "blocked_missing_governed_operator_value_binding_record_evidence",
            "execution_worker_admission_allowed": False,
            "dispatch_allowed": False,
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_send_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
        },
        "receipt": _preflight_receipt(
            receipt_id=f"pa_receipt_operator_reapproval_decision_receipt_value_binding_record_admission_preflight_{suffix}",
            request_id=request_id,
            skill_id=skill_id,
            risk_level=risk_level,
            approval_id=approval_id,
            timestamp=timestamp,
        ),
    }


def _preflight_receipt(
    *,
    receipt_id: str,
    request_id: str,
    skill_id: str,
    risk_level: str,
    approval_id: str,
    timestamp: str,
) -> dict[str, Any]:
    return {
        "receipt_id": receipt_id,
        "request_id": request_id,
        "skill_id": skill_id,
        "mode": "execute_with_approval",
        "risk_level": risk_level,
        "inputs_used": [
            "operator_reapproval_decision_receipt_value_binding_record_guard",
            "operator_reapproval_decision_receipt_value_binding_record_admission_preflight_policy",
        ],
        "connectors_used": ["gmail"] if skill_id.startswith("email.") else [],
        "decision": "blocked",
        "approval_required": True,
        "approval_ref": approval_id,
        "actions_taken": [
            "operator_reapproval_decision_receipt_value_binding_record_guard_ref_recorded",
            "missing_operator_value_binding_record_evidence_recorded",
            "binding_record_admission_denied",
            "receipt_created",
        ],
        "actions_not_taken": [
            "operator_reapproval_decision_value_not_bound",
            "operator_identity_ref_not_bound",
            "operator_signature_ref_not_bound",
            "operator_reapproval_receipt_not_bound",
            "binding_record_candidate_not_accepted",
            "binding_record_not_created",
            "binding_record_not_admitted",
            "execution_worker_not_admitted",
            "dispatch_lease_not_activated",
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
        "evidence_refs": [f"proof://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-admission-preflight/{approval_id}"],
        "memory_observation_refs": [],
        "replay_refs": [f"replay://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-admission-preflight/{approval_id}"],
        "outcome": "GovernanceBlocked",
        "metadata": {
            "foundation_only": True,
            "operator_reapproval_decision_receipt_value_binding_record_admission_preflight_is_execution": False,
            "record_guard_ref_bound": True,
            "operator_submitted_value_required": True,
            "operator_value_collected": False,
            "explicit_operator_value_present": False,
            "operator_value_bound": False,
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


def _assert_record_guard_boundary(source_envelope: Mapping[str, Any]) -> None:
    effect_boundary = _require_mapping(source_envelope.get("effect_boundary"), "effect_boundary")
    for field_name in (
        "operator_reapproval_decision_receipt_value_binding_record_guard_allowed",
        "value_binding_contract_ref_binding_allowed",
        "future_value_binding_record_preflight_allowed",
        "candidate_value_binding_record_requirements_allowed",
        "operator_submitted_value_required",
        "operator_identity_ref_required",
        "operator_signature_ref_required",
        "decision_receipt_required",
    ):
        if effect_boundary.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"value binding record guard effect_boundary.{field_name} must be true")
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
            raise PersonalAssistantInvariantError(f"value binding record guard effect_boundary.{field_name} must be false")
    if _require_mapping(source_envelope.get("assurance"), "assurance").get("outcome") != "AwaitingEvidence":
        raise PersonalAssistantInvariantError("value binding record guard assurance.outcome must be AwaitingEvidence")


def _assert_record_guard_item_boundary(
    source_guard_id: str,
    candidate_requirements: Mapping[str, Any],
    execution_block: Mapping[str, Any],
) -> None:
    if tuple(candidate_requirements.get("allowed_decision_values", ())) != _ALLOWED_DECISION_VALUES:
        raise PersonalAssistantInvariantError(f"{source_guard_id}: allowed_decision_values must preserve allowed decision values")
    for field_name in (
        "requires_explicit_operator_value",
        "requires_operator_identity_ref",
        "requires_operator_signature_ref",
        "requires_decision_receipt_ref",
        "requires_value_binding_contract_ref",
    ):
        if candidate_requirements.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"{source_guard_id}: record_candidate_requirements.{field_name} must be true")
    for field_name in (
        "accepted_value_present",
        "operator_value_bound",
        "operator_identity_ref_bound",
        "operator_signature_ref_bound",
        "decision_receipt_ref_bound",
        "binding_record_candidate_accepted",
        "binding_record_created",
        "grants_execution_authority",
    ):
        if candidate_requirements.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"{source_guard_id}: record_candidate_requirements.{field_name} must be false")
    if execution_block.get("execution_worker_admission_state") != "blocked_pending_value_binding_record_admission_preflight":
        raise PersonalAssistantInvariantError(f"{source_guard_id}: execution_admission_block.execution_worker_admission_state must remain blocked")
    for field_name in (
        "execution_worker_admission_allowed",
        "dispatch_allowed",
        "live_connector_execution_allowed",
        "connector_mutation_allowed",
        "external_send_allowed",
        "system_of_record_write_allowed",
        "memory_write_allowed",
    ):
        if execution_block.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"{source_guard_id}: execution_admission_block.{field_name} must be false")


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

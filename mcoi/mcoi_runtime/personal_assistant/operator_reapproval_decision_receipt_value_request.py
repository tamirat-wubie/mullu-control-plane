"""Purpose: operator reapproval decision receipt value-request envelopes.
Governance scope: receipt-intake refs, future operator decision receipt value
requirements, private-payload redaction, and no-execution boundaries.
Dependencies: personal-assistant operator reapproval decision receipt intake
runtime and contracts.
Invariants:
  - Value-request preflight records the future governed receipt fields only.
  - Operator decision value, identity refs, signatures, and decision receipts
    are required but remain absent.
  - Execution-worker admission, dispatch, live connector execution, connector
    mutation, external sends, memory writes, system-of-record writes, deployment
    mutation, and readiness claims remain false.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .operator_reapproval_decision_receipt_intake import (
    build_default_personal_assistant_operator_reapproval_decision_receipt_intake,
)


DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_REQUEST_SET_ID = (
    "pa_operator_reapproval_decision_receipt_value_request_foundation_001"
)
DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_REQUEST_GENERATED_AT = "2026-06-14T00:13:00+00:00"

_VALUE_REQUEST_SET_ID_PATTERN = re.compile(r"^pa_operator_reapproval_decision_receipt_value_request_[a-z0-9][a-z0-9_:-]*$")
_VALUE_REQUEST_ID_PATTERN = re.compile(r"^pa_operator_reapproval_decision_receipt_value_request_item_[a-z0-9][a-z0-9_:-]*$")
_DIGEST_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")
_ACCEPTED_DECISION_VALUES = ("approved", "rejected", "revised", "expired")
_EFFECT_BOUNDARY = {
    "operator_reapproval_decision_receipt_value_request_allowed": True,
    "receipt_intake_ref_binding_allowed": True,
    "decision_receipt_value_required": True,
    "operator_identity_ref_required": True,
    "operator_signature_ref_required": True,
    "operator_receipt_submission_required": True,
    "decision_value_present": False,
    "fresh_operator_decision_present": False,
    "operator_identity_ref_present": False,
    "operator_signature_ref_present": False,
    "operator_reapproval_receipt_present": False,
    "decision_receipt_present": False,
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
    "receipt_intake_payload_projection": "ref_only",
    "decision_value_projection": "absent",
    "operator_signature_projection": "absent",
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
        "operator_signature",
        "raw_decision_receipt",
    }
)
_ALLOWED_POLICY_FIELD_NAMES = frozenset(
    {
        "private_payload_policy",
        "raw_private_payload_serialized",
        "secret_values_serialized",
        "receipt_intake_payload_projection",
        "decision_value_projection",
        "operator_signature_projection",
        "receipt_intake_digest",
        "value_request_digest",
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


def build_default_personal_assistant_operator_reapproval_decision_receipt_value_request(
    *,
    generated_at: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_REQUEST_GENERATED_AT,
    value_request_set_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_REQUEST_SET_ID,
) -> dict[str, Any]:
    """Build deterministic no-effect operator decision receipt value request."""
    return build_personal_assistant_operator_reapproval_decision_receipt_value_request_envelope(
        generated_at=generated_at,
        value_request_set_id=value_request_set_id,
        operator_reapproval_decision_receipt_intake=(
            build_default_personal_assistant_operator_reapproval_decision_receipt_intake()
        ),
    )


def build_personal_assistant_operator_reapproval_decision_receipt_value_request_envelope(
    *,
    generated_at: str,
    operator_reapproval_decision_receipt_intake: Mapping[str, Any],
    value_request_set_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_REQUEST_SET_ID,
) -> dict[str, Any]:
    """Build no-effect value requests from receipt-intake preflight evidence."""
    timestamp = _require_non_empty_text(generated_at, "generated_at")
    envelope_id = _require_pattern(value_request_set_id, "value_request_set_id", _VALUE_REQUEST_SET_ID_PATTERN)
    source_envelope = _require_mapping(
        operator_reapproval_decision_receipt_intake,
        "operator_reapproval_decision_receipt_intake",
    )
    _scan_private_or_secret_payload(source_envelope, path="operator_reapproval_decision_receipt_intake")
    _assert_intake_boundary(source_envelope)
    source_intake_set_id = _require_non_empty_text(source_envelope.get("intake_set_id"), "intake_set_id")

    value_requests: list[dict[str, Any]] = []
    value_request_ids: list[str] = []
    source_intake_ids: list[str] = []
    receipt_ids: list[str] = []
    source_intakes = source_envelope.get("intakes")
    if isinstance(source_intakes, (str, bytes)) or not isinstance(source_intakes, Sequence):
        raise PersonalAssistantInvariantError("operator_reapproval_decision_receipt_intake.intakes must be a sequence")
    for source_intake in source_intakes:
        if not isinstance(source_intake, Mapping):
            raise PersonalAssistantInvariantError("operator reapproval decision receipt intake item must be a mapping")
        value_request = _value_request_item(source_intake_set_id, source_intake, timestamp=timestamp)
        if value_request["value_request_id"] in value_request_ids:
            raise PersonalAssistantInvariantError(f"duplicate value_request_id {value_request['value_request_id']}")
        value_request_ids.append(value_request["value_request_id"])
        source_intake_ids.append(value_request["source_intake_id"])
        receipt_ids.append(value_request["receipt"]["receipt_id"])
        value_requests.append(value_request)
    if not value_requests:
        raise PersonalAssistantInvariantError("operator reapproval decision receipt value request requires at least one intake")

    envelope = {
        "value_request_set_id": envelope_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "operator_reapproval_decision_receipt_intake",
        "source_operator_reapproval_decision_receipt_intake_set_id": source_intake_set_id,
        "value_request_count": len(value_requests),
        "value_request_ids": value_request_ids,
        "source_intake_ids": source_intake_ids,
        "receipt_ids": receipt_ids,
        "value_requests": value_requests,
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "assurance": {
            "assurance_id": "personal_assistant_operator_reapproval_decision_receipt_value_request_no_effect_assurance",
            "outcome": "AwaitingEvidence",
            "foundation_only": True,
            "ready_for_execution_worker_admission": False,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "checked_controls": [
                "operator_reapproval_decision_receipt_intake_required",
                "receipt_intake_ref_bound",
                "decision_value_request_recorded",
                "operator_identity_ref_request_recorded",
                "operator_signature_ref_request_recorded",
                "decision_receipt_still_absent",
                "no_execution_worker_admission",
                "no_dispatch",
                "no_live_connector_execution",
            ],
            "blocking_reasons": [
                "operator_decision_value_not_submitted",
                "operator_identity_ref_not_submitted",
                "operator_signature_ref_not_submitted",
                "operator_reapproval_decision_receipt_not_submitted",
                "execution_worker_admission_not_requested",
            ],
            "next_action": "collect a governed operator decision receipt value in a separate effect-reviewed artifact",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "operator_reapproval_decision_receipt_value_request_evidence_only",
            "runtime_boundary": "value_request_records_required_future_decision_receipt_fields_without_collecting_them",
            "decision_value_present": False,
            "fresh_operator_decision_present": False,
            "operator_identity_ref_present": False,
            "operator_signature_ref_present": False,
            "operator_reapproval_receipt_present": False,
            "decision_receipt_present": False,
            "execution_worker_admission_allowed": False,
            "dispatch_allowed": False,
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_send_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
        },
    }
    _scan_private_or_secret_payload(envelope, path="envelope")
    return envelope


def _value_request_item(source_intake_set_id: str, source_intake: Mapping[str, Any], *, timestamp: str) -> dict[str, Any]:
    source_intake_id = _require_non_empty_text(source_intake.get("intake_id"), "source_intake_id")
    approval_id = _require_non_empty_text(source_intake.get("approval_id"), "approval_id")
    request_id = _require_non_empty_text(source_intake.get("request_id"), "request_id")
    plan_id = _require_non_empty_text(source_intake.get("plan_id"), "plan_id")
    skill_id = _require_non_empty_text(source_intake.get("skill_id"), "skill_id")
    risk_level = _require_non_empty_text(source_intake.get("risk_level"), "risk_level")
    absence_ref = _require_mapping(source_intake.get("absence_witness_ref"), "absence_witness_ref")
    intake_request = _require_mapping(source_intake.get("receipt_intake_request"), "receipt_intake_request")
    execution_block = _require_mapping(source_intake.get("execution_admission_block"), "execution_admission_block")
    _assert_intake_item_boundary(source_intake_id, approval_id, absence_ref, intake_request, execution_block)
    suffix = approval_id.removeprefix("pa_approval_")
    value_request_id = _require_pattern(
        f"pa_operator_reapproval_decision_receipt_value_request_item_{suffix}",
        "value_request_id",
        _VALUE_REQUEST_ID_PATTERN,
    )
    receipt_intake_digest = _require_non_empty_text(
        intake_request.get("receipt_intake_digest"),
        "receipt_intake_digest",
    )
    return {
        "value_request_id": value_request_id,
        "source_intake_id": source_intake_id,
        "approval_id": approval_id,
        "request_id": request_id,
        "plan_id": plan_id,
        "skill_id": skill_id,
        "risk_level": risk_level,
        "receipt_intake_ref": {
            "source_intake_set_id": source_intake_set_id,
            "source_intake_id": source_intake_id,
            "receipt_intake_ref": str(intake_request.get("receipt_intake_ref", "")),
            "receipt_intake_digest": receipt_intake_digest,
            "accepted_decision_values": list(_ACCEPTED_DECISION_VALUES),
            "decision_receipt_required": True,
            "decision_receipt_present": False,
            "execution_worker_admission_allowed": False,
        },
        "decision_value_request": {
            "value_request_ref": f"receipt://personal-assistant/operator-reapproval-decision-value-request/{approval_id}",
            "value_request_digest": _digest_for("operator-reapproval-decision-receipt-value-request", approval_id, request_id, plan_id, skill_id),
            "accepted_decision_values": list(_ACCEPTED_DECISION_VALUES),
            "operator_decision_value_required": True,
            "operator_decision_value_present": False,
            "operator_identity_ref_required": True,
            "operator_identity_ref_present": False,
            "operator_signature_ref_required": True,
            "operator_signature_ref_present": False,
            "decision_receipt_required": True,
            "decision_receipt_present": False,
            "raw_operator_decision_serialized": False,
            "secret_values_serialized": False,
            "submission_payload_projection": "operator_supplied_receipt_required_but_absent",
        },
        "execution_admission_block": {
            "execution_worker_admission_state": "blocked_pending_operator_reapproval_decision_receipt_value",
            "execution_worker_admission_allowed": False,
            "dispatch_allowed": False,
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_send_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
        },
        "receipt": _value_request_receipt(
            receipt_id=f"pa_receipt_operator_reapproval_decision_receipt_value_request_{suffix}",
            request_id=request_id,
            skill_id=skill_id,
            risk_level=risk_level,
            approval_id=approval_id,
            timestamp=timestamp,
        ),
    }


def _value_request_receipt(
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
        "inputs_used": ["operator_reapproval_decision_receipt_intake", "operator_reapproval_decision_receipt_value_request_policy"],
        "connectors_used": ["gmail"] if skill_id.startswith("email.") else [],
        "decision": "deferred",
        "approval_required": True,
        "approval_ref": approval_id,
        "actions_taken": [
            "operator_reapproval_decision_receipt_intake_ref_recorded",
            "operator_reapproval_decision_receipt_value_request_recorded",
            "execution_worker_admission_blocker_recorded",
            "receipt_created",
        ],
        "actions_not_taken": [
            "operator_reapproval_decision_value_not_recorded",
            "operator_identity_ref_not_bound",
            "operator_signature_ref_not_bound",
            "operator_reapproval_receipt_not_created",
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
            "operator_decision_absent",
            "operator_identity_ref_absent",
            "operator_signature_absent",
            "private_connector_payload_not_serialized",
        ],
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": "ref_only",
            "body_projection": "none",
        },
        "timestamp": timestamp,
        "evidence_refs": [f"proof://personal-assistant/operator-reapproval-decision-receipt-value-request/{approval_id}"],
        "memory_observation_refs": [],
        "replay_refs": [f"replay://personal-assistant/operator-reapproval-decision-receipt-value-request/{approval_id}"],
        "outcome": "AwaitingEvidence",
        "metadata": {
            "foundation_only": True,
            "operator_reapproval_decision_receipt_value_request_is_execution": False,
            "receipt_intake_ref_bound": True,
            "operator_decision_value_required": True,
            "operator_decision_value_present": False,
            "operator_identity_ref_required": True,
            "operator_identity_ref_present": False,
            "operator_signature_ref_required": True,
            "operator_signature_ref_present": False,
            "decision_receipt_required": True,
            "decision_receipt_present": False,
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


def _assert_intake_boundary(source_envelope: Mapping[str, Any]) -> None:
    effect_boundary = _require_mapping(source_envelope.get("effect_boundary"), "effect_boundary")
    for field_name in (
        "operator_reapproval_decision_receipt_intake_preflight_allowed",
        "receipt_absence_ref_binding_allowed",
        "decision_receipt_submission_request_allowed",
        "decision_receipt_required",
        "decision_value_required",
        "operator_identity_ref_required",
        "operator_signature_ref_required",
    ):
        if effect_boundary.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"receipt intake effect_boundary.{field_name} must be true")
    for field_name in (
        "decision_value_present",
        "fresh_operator_decision_present",
        "operator_identity_ref_present",
        "operator_signature_ref_present",
        "operator_reapproval_receipt_present",
        "decision_receipt_present",
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
            raise PersonalAssistantInvariantError(f"receipt intake effect_boundary.{field_name} must be false")


def _assert_intake_item_boundary(
    source_intake_id: str,
    approval_id: str,
    absence_ref: Mapping[str, Any],
    intake_request: Mapping[str, Any],
    execution_block: Mapping[str, Any],
) -> None:
    expected_receipt_ref = f"receipt://personal-assistant/operator-reapproval-decision/{approval_id}"
    expected_intake_ref = f"receipt://personal-assistant/operator-reapproval-decision-intake/{approval_id}"
    if absence_ref.get("required_receipt_ref") != expected_receipt_ref:
        raise PersonalAssistantInvariantError(f"{source_intake_id}: required_receipt_ref must match approval_id")
    if intake_request.get("receipt_intake_ref") != expected_intake_ref:
        raise PersonalAssistantInvariantError(f"{source_intake_id}: receipt_intake_ref must match approval_id")
    if tuple(intake_request.get("accepted_decision_values", ())) != _ACCEPTED_DECISION_VALUES:
        raise PersonalAssistantInvariantError(f"{source_intake_id}: accepted_decision_values must be canonical")
    for field_name in (
        "operator_decision_value_required",
        "operator_identity_ref_required",
        "operator_signature_ref_required",
        "decision_receipt_required",
    ):
        if intake_request.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"{source_intake_id}: receipt_intake_request.{field_name} must be true")
    for field_name in (
        "operator_decision_value_present",
        "operator_identity_ref_present",
        "operator_signature_ref_present",
        "decision_receipt_present",
        "raw_operator_decision_serialized",
        "secret_values_serialized",
    ):
        if intake_request.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"{source_intake_id}: receipt_intake_request.{field_name} must be false")
    for field_name in (
        "decision_receipt_present",
        "execution_worker_admission_allowed",
    ):
        if absence_ref.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"{source_intake_id}: absence_witness_ref.{field_name} must be false")
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
            raise PersonalAssistantInvariantError(f"{source_intake_id}: execution_admission_block.{field_name} must be false")


def _digest_for(kind: str, approval_id: str, request_id: str, plan_id: str, skill_id: str) -> str:
    material = f"personal-assistant:{kind}:{approval_id}:{request_id}:{plan_id}:{skill_id}".encode("utf-8")
    digest = f"sha256:{hashlib.sha256(material).hexdigest()}"
    if not _DIGEST_PATTERN.fullmatch(digest):
        raise PersonalAssistantInvariantError(f"{kind} digest has invalid shape")
    return digest


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
    elif isinstance(payload, str):
        if any(pattern.search(payload) for pattern in _SECRET_VALUE_PATTERNS):
            raise PersonalAssistantInvariantError(f"{path}: secret-like value must not be serialized")

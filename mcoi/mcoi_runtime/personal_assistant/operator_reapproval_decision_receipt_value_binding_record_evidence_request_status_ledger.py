"""Purpose: operator value-binding evidence request status ledger.
Governance scope: request-only evidence slot status records, source request
refs, private-payload redaction, and no-execution boundaries.
Dependencies: personal-assistant operator reapproval decision receipt value
binding record evidence request runtime and contracts.
Invariants:
  - The ledger records requested/not-submitted status only.
  - No evidence submission, acceptance, rejection, raw operator value, identity,
    signature, receipt payload, connector payload, or secret is serialized.
  - Binding-record admission, execution-worker admission, dispatch, live
    connector execution, connector mutation, memory writes, system-of-record
    writes, deployment mutation, and readiness claims remain false.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .operator_reapproval_decision_receipt_value_binding_record_evidence_request import (
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request,
)


DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_EVIDENCE_REQUEST_STATUS_LEDGER_ID = (
    "pa_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger_foundation_001"
)
DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_EVIDENCE_REQUEST_STATUS_LEDGER_GENERATED_AT = (
    "2026-06-14T00:23:00+00:00"
)

_LEDGER_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger_[a-z0-9][a-z0-9_:-]*$"
)
_STATUS_RECORD_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_record_[a-z0-9][a-z0-9_:-]*$"
)
_EVIDENCE_KINDS = (
    "operator_decision_value_ref",
    "operator_identity_ref",
    "operator_signature_ref",
    "operator_reapproval_decision_receipt_ref",
)
_EFFECT_BOUNDARY = {
    "operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger_allowed": True,
    "evidence_request_ref_binding_allowed": True,
    "requested_not_submitted_status_recording_allowed": True,
    "operator_input_still_required": True,
    "status_ledger_is_submission": False,
    "status_ledger_is_acceptance": False,
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
    "evidence_request_projection": "ref_only",
    "status_record_projection": "requested_not_submitted_only",
    "operator_decision_value_projection": "absent",
    "operator_identity_ref_projection": "absent",
    "operator_signature_ref_projection": "absent",
    "decision_receipt_projection": "absent",
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
        "evidence_request_projection",
        "status_record_projection",
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


def build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger(
    *,
    generated_at: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_EVIDENCE_REQUEST_STATUS_LEDGER_GENERATED_AT,
    status_ledger_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_EVIDENCE_REQUEST_STATUS_LEDGER_ID,
) -> dict[str, Any]:
    """Build deterministic requested/not-submitted evidence request status ledger."""

    return build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger_envelope(
        generated_at=generated_at,
        status_ledger_id=status_ledger_id,
        operator_reapproval_decision_receipt_value_binding_record_evidence_request=(
            build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request()
        ),
    )


def build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger_envelope(
    *,
    generated_at: str,
    operator_reapproval_decision_receipt_value_binding_record_evidence_request: Mapping[str, Any],
    status_ledger_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_EVIDENCE_REQUEST_STATUS_LEDGER_ID,
) -> dict[str, Any]:
    """Build status records from request-only value-binding evidence slots."""

    timestamp = _require_non_empty_text(generated_at, "generated_at")
    ledger_id = _require_pattern(status_ledger_id, "status_ledger_id", _LEDGER_ID_PATTERN)
    source_envelope = _require_mapping(
        operator_reapproval_decision_receipt_value_binding_record_evidence_request,
        "operator_reapproval_decision_receipt_value_binding_record_evidence_request",
    )
    _scan_private_or_secret_payload(source_envelope, path="operator_reapproval_decision_receipt_value_binding_record_evidence_request")
    _assert_evidence_request_boundary(source_envelope)
    source_request_set_id = _require_non_empty_text(
        source_envelope.get("value_binding_record_evidence_request_set_id"),
        "value_binding_record_evidence_request_set_id",
    )

    records: list[dict[str, Any]] = []
    status_record_ids: list[str] = []
    evidence_request_ids: list[str] = []
    receipt_ids: list[str] = []
    request_slots = source_envelope.get("evidence_requests")
    if isinstance(request_slots, (str, bytes)) or not isinstance(request_slots, Sequence):
        raise PersonalAssistantInvariantError("operator value-binding evidence_requests must be a sequence")
    for request_slot in request_slots:
        if not isinstance(request_slot, Mapping):
            raise PersonalAssistantInvariantError("operator value-binding evidence request slot must be a mapping")
        _assert_request_slot_boundary(request_slot)
        status_record = _status_record(source_request_set_id, request_slot, timestamp=timestamp)
        if status_record["status_record_id"] in status_record_ids:
            raise PersonalAssistantInvariantError(f"duplicate status_record_id {status_record['status_record_id']}")
        status_record_ids.append(status_record["status_record_id"])
        evidence_request_ids.append(status_record["evidence_request_id"])
        receipt_ids.append(status_record["receipt"]["receipt_id"])
        records.append(status_record)
    if not records:
        raise PersonalAssistantInvariantError("operator value-binding evidence request status ledger requires at least one status record")

    envelope = {
        "status_ledger_id": ledger_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "operator_reapproval_decision_receipt_value_binding_record_evidence_request",
        "source_operator_reapproval_decision_receipt_value_binding_record_evidence_request_set_id": source_request_set_id,
        "ledger_state": "requested_not_submitted",
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "status_record_count": len(records),
        "status_record_ids": status_record_ids,
        "evidence_request_ids": evidence_request_ids,
        "receipt_ids": receipt_ids,
        "status_records": records,
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "summary": _summary(records),
        "assurance": {
            "assurance_id": "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger_no_effect_assurance",
            "outcome": "AwaitingEvidence",
            "foundation_only": True,
            "request_status_only": True,
            "ready_for_evidence_submission": False,
            "ready_for_evidence_acceptance": False,
            "ready_for_binding_record_admission": False,
            "ready_for_execution_worker_admission": False,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "checked_controls": [
                "evidence_request_required",
                "evidence_request_ref_bound",
                "requested_not_submitted_status_recorded",
                "no_evidence_submission",
                "no_evidence_acceptance",
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
            "next_action": "collect separate governed evidence submission refs in a later path without raw operator value serialization",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger",
            "runtime_boundary": "status_ledger_records_requested_not_submitted_only",
            "request_status_only": True,
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


def _status_record(source_request_set_id: str, request_slot: Mapping[str, Any], *, timestamp: str) -> dict[str, Any]:
    evidence_request_id = _require_non_empty_text(request_slot.get("evidence_request_id"), "evidence_request_id")
    evidence_kind = _require_non_empty_text(request_slot.get("evidence_kind"), "evidence_kind")
    approval_id = _require_non_empty_text(request_slot.get("approval_id"), "approval_id")
    request_id = _require_non_empty_text(request_slot.get("request_id"), "request_id")
    plan_id = _require_non_empty_text(request_slot.get("plan_id"), "plan_id")
    skill_id = _require_non_empty_text(request_slot.get("skill_id"), "skill_id")
    risk_level = _require_non_empty_text(request_slot.get("risk_level"), "risk_level")
    suffix = approval_id.removeprefix("pa_approval_")
    status_record_id = _require_pattern(
        f"pa_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_record_{evidence_kind}_{suffix}",
        "status_record_id",
        _STATUS_RECORD_ID_PATTERN,
    )
    return {
        "status_record_id": status_record_id,
        "evidence_request_id": evidence_request_id,
        "evidence_kind": evidence_kind,
        "approval_id": approval_id,
        "request_id": request_id,
        "plan_id": plan_id,
        "skill_id": skill_id,
        "risk_level": risk_level,
        "evidence_request_ref": {
            "source_evidence_request_set_id": source_request_set_id,
            "source_evidence_request_id": evidence_request_id,
            "source_outcome": "AwaitingEvidence",
            "request_only": True,
            "evidence_submitted": False,
            "evidence_accepted": False,
            "authority_granted": False,
        },
        "status": {
            "ledger_state": "requested_not_submitted",
            "proof_state": "Unknown",
            "operator_input_required": True,
            "request_only": True,
            "status_is_not_submission": True,
            "status_is_not_acceptance": True,
            "evidence_submitted": False,
            "evidence_accepted": False,
            "evidence_rejected": False,
            "submitted_evidence_refs": [],
            "accepted_evidence_refs": [],
            "rejected_evidence_refs": [],
            "requirement_satisfied": False,
        },
        "authority_status": {
            "operator_value_bound": False,
            "operator_identity_ref_bound": False,
            "operator_signature_ref_bound": False,
            "decision_receipt_ref_bound": False,
            "binding_record_created": False,
            "binding_record_admitted": False,
            "authority_granted": False,
            "execution_worker_admission_allowed": False,
            "dispatch_allowed": False,
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
        },
        "receipt": _status_receipt(
            receipt_id=f"pa_receipt_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_{evidence_kind}_{suffix}",
            request_id=request_id,
            skill_id=skill_id,
            risk_level=risk_level,
            approval_id=approval_id,
            evidence_kind=evidence_kind,
            timestamp=timestamp,
        ),
    }


def _status_receipt(
    *,
    receipt_id: str,
    request_id: str,
    skill_id: str,
    risk_level: str,
    approval_id: str,
    evidence_kind: str,
    timestamp: str,
) -> dict[str, Any]:
    return {
        "receipt_id": receipt_id,
        "request_id": request_id,
        "skill_id": skill_id,
        "mode": "execute_with_approval",
        "risk_level": risk_level,
        "inputs_used": [
            "operator_reapproval_decision_receipt_value_binding_record_evidence_request",
            "operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_policy",
        ],
        "connectors_used": ["gmail"] if skill_id.startswith("email.") else [],
        "decision": "blocked",
        "approval_required": True,
        "approval_ref": approval_id,
        "actions_taken": [
            f"{evidence_kind}_requested_not_submitted_status_recorded",
            "request_status_receipt_created",
        ],
        "actions_not_taken": [
            "operator_evidence_not_submitted",
            "operator_evidence_not_accepted",
            "raw_operator_decision_value_not_collected",
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
        "evidence_refs": [f"proof://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-evidence-request-status/{approval_id}/{evidence_kind}"],
        "memory_observation_refs": [],
        "replay_refs": [f"replay://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-evidence-request-status/{approval_id}/{evidence_kind}"],
        "outcome": "AwaitingEvidence",
        "metadata": {
            "foundation_only": True,
            "operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger_is_execution": False,
            "evidence_kind": evidence_kind,
            "request_status_only": True,
            "evidence_submitted": False,
            "evidence_accepted": False,
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


def _summary(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    statuses = [_require_mapping(record.get("status"), "status") for record in records]
    authorities = [_require_mapping(record.get("authority_status"), "authority_status") for record in records]
    return {
        "status_record_count": len(records),
        "requested_not_submitted_count": sum(1 for status in statuses if status.get("ledger_state") == "requested_not_submitted"),
        "unknown_proof_state_count": sum(1 for status in statuses if status.get("proof_state") == "Unknown"),
        "operator_input_required_count": sum(1 for status in statuses if status.get("operator_input_required") is True),
        "submitted_evidence_count": sum(1 for status in statuses if status.get("evidence_submitted") is True),
        "accepted_evidence_count": sum(1 for status in statuses if status.get("evidence_accepted") is True),
        "rejected_evidence_count": sum(1 for status in statuses if status.get("evidence_rejected") is True),
        "satisfied_requirement_count": sum(1 for status in statuses if status.get("requirement_satisfied") is True),
        "authority_grant_count": sum(1 for status in authorities if status.get("authority_granted") is True),
        "binding_record_creation_count": sum(1 for status in authorities if status.get("binding_record_created") is True),
    }


def _assert_evidence_request_boundary(source_envelope: Mapping[str, Any]) -> None:
    effect_boundary = _require_mapping(source_envelope.get("effect_boundary"), "effect_boundary")
    for field_name in (
        "operator_reapproval_decision_receipt_value_binding_record_evidence_request_allowed",
        "value_binding_record_admission_preflight_ref_binding_allowed",
        "operator_evidence_slot_request_allowed",
        "operator_input_request_allowed",
        "evidence_request_issued",
    ):
        if effect_boundary.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"value binding evidence request effect_boundary.{field_name} must be true")
    for field_name in (
        "evidence_request_is_submission",
        "evidence_request_is_acceptance",
        "evidence_submitted",
        "evidence_accepted",
        "evidence_rejected",
        "operator_value_collected",
        "explicit_operator_value_present",
        "operator_value_bound",
        "binding_record_created",
        "binding_record_admitted",
        "authority_granted",
        "execution_worker_admission_allowed",
        "dispatch_allowed",
        "live_connector_execution_allowed",
        "connector_mutation_allowed",
        "system_of_record_write_allowed",
        "memory_write_allowed",
        "deployment_mutation_allowed",
        "nested_mind_live_activation_allowed",
        "public_readiness_claim_allowed",
    ):
        if effect_boundary.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"value binding evidence request effect_boundary.{field_name} must be false")
    if source_envelope.get("outcome") != "AwaitingEvidence":
        raise PersonalAssistantInvariantError("value binding evidence request outcome must remain AwaitingEvidence")


def _assert_request_slot_boundary(request_slot: Mapping[str, Any]) -> None:
    evidence_kind = _require_non_empty_text(request_slot.get("evidence_kind"), "evidence_kind")
    if evidence_kind not in _EVIDENCE_KINDS:
        raise PersonalAssistantInvariantError("evidence request slot kind must remain governed")
    contract = _require_mapping(request_slot.get("request_contract"), "request_contract")
    if contract.get("request_state") != "requested" or contract.get("proof_state") != "Unknown":
        raise PersonalAssistantInvariantError("evidence request contract must remain requested with Unknown proof state")
    for field_name in ("required", "request_only", "ref_only", "evidence_submission_required_later"):
        if contract.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"evidence request contract.{field_name} must be true")
    for field_name in ("raw_value_requested", "raw_payload_requested"):
        if contract.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"evidence request contract.{field_name} must be false")
    submission_state = _require_mapping(request_slot.get("submission_state"), "submission_state")
    for field_name in (
        "evidence_submitted",
        "evidence_accepted",
        "evidence_rejected",
        "requirement_satisfied",
        "authority_granted",
    ):
        if submission_state.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"evidence request submission_state.{field_name} must be false")
    for field_name in ("submitted_evidence_refs", "accepted_evidence_refs", "rejected_evidence_refs"):
        if submission_state.get(field_name) != []:
            raise PersonalAssistantInvariantError(f"evidence request submission_state.{field_name} must remain empty")


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

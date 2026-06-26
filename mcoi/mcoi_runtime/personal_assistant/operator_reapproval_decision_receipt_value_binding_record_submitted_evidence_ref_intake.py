"""Purpose: operator value-binding submitted evidence ref intake.
Governance scope: ref-only submitted evidence intake, status-ledger refs,
private-payload redaction, and no-execution boundaries.
Dependencies: personal-assistant operator reapproval decision receipt value
binding record evidence request status ledger runtime and contracts.
Invariants:
  - Submitted evidence is represented by governed refs only.
  - Raw operator values, identity payloads, signatures, decision receipt
    payloads, connector payloads, and secrets are not collected or serialized.
  - Submitted refs are not evidence acceptance, value binding, record
    admission, execution-worker admission, dispatch, live connector execution,
    connector mutation, memory writes, system-of-record writes, deployment
    mutation, or readiness claims.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger import (
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger,
)


DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_SUBMITTED_EVIDENCE_REF_INTAKE_ID = (
    "pa_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake_foundation_001"
)
DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_SUBMITTED_EVIDENCE_REF_INTAKE_GENERATED_AT = (
    "2026-06-14T00:24:00+00:00"
)

_INTAKE_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake_[a-z0-9][a-z0-9_:-]*$"
)
_SUBMISSION_RECORD_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_record_[a-z0-9][a-z0-9_:-]*$"
)
_EVIDENCE_KINDS = (
    "operator_decision_value_ref",
    "operator_identity_ref",
    "operator_signature_ref",
    "operator_reapproval_decision_receipt_ref",
)
_EFFECT_BOUNDARY = {
    "operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake_allowed": True,
    "evidence_request_status_ledger_ref_binding_allowed": True,
    "submitted_evidence_ref_recording_allowed": True,
    "submitted_evidence_refs_present": True,
    "evidence_submitted": True,
    "evidence_ref_only": True,
    "status_ledger_is_source": True,
    "raw_evidence_payload_present": False,
    "raw_operator_value_present": False,
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
    "status_ledger_projection": "ref_only",
    "submitted_evidence_projection": "ref_only",
    "operator_decision_value_projection": "absent",
    "operator_identity_ref_projection": "absent",
    "operator_signature_ref_projection": "absent",
    "decision_receipt_projection": "absent",
    "evidence_acceptance_projection": "absent",
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
        "raw_submitted_evidence",
        "submitted_value",
    }
)
_ALLOWED_POLICY_FIELD_NAMES = frozenset(
    {
        "private_payload_policy",
        "raw_private_payload_serialized",
        "secret_values_serialized",
        "status_ledger_projection",
        "submitted_evidence_projection",
        "operator_decision_value_projection",
        "operator_identity_ref_projection",
        "operator_signature_ref_projection",
        "decision_receipt_projection",
        "evidence_acceptance_projection",
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


def build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake(
    *,
    generated_at: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_SUBMITTED_EVIDENCE_REF_INTAKE_GENERATED_AT,
    submitted_evidence_ref_intake_id: str = (
        DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_SUBMITTED_EVIDENCE_REF_INTAKE_ID
    ),
) -> dict[str, Any]:
    """Build deterministic ref-only submitted evidence intake."""

    return build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake_envelope(
        generated_at=generated_at,
        submitted_evidence_ref_intake_id=submitted_evidence_ref_intake_id,
        operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger=(
            build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger()
        ),
    )


def build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake_envelope(
    *,
    generated_at: str,
    operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger: Mapping[str, Any],
    submitted_evidence_ref_intake_id: str = (
        DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_SUBMITTED_EVIDENCE_REF_INTAKE_ID
    ),
) -> dict[str, Any]:
    """Build ref-only submitted evidence intake records from requested slots."""

    timestamp = _require_non_empty_text(generated_at, "generated_at")
    intake_id = _require_pattern(submitted_evidence_ref_intake_id, "submitted_evidence_ref_intake_id", _INTAKE_ID_PATTERN)
    source_envelope = _require_mapping(
        operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger,
        "operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger",
    )
    _scan_private_or_secret_payload(source_envelope, path="operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger")
    _assert_status_ledger_boundary(source_envelope)
    source_status_ledger_id = _require_non_empty_text(source_envelope.get("status_ledger_id"), "status_ledger_id")

    submission_records: list[dict[str, Any]] = []
    submission_record_ids: list[str] = []
    status_record_ids: list[str] = []
    submitted_evidence_refs: list[str] = []
    receipt_ids: list[str] = []
    status_records = source_envelope.get("status_records")
    if isinstance(status_records, (str, bytes)) or not isinstance(status_records, Sequence):
        raise PersonalAssistantInvariantError("submitted evidence ref intake requires status_records sequence")
    for status_record in status_records:
        if not isinstance(status_record, Mapping):
            raise PersonalAssistantInvariantError("submitted evidence ref intake status record must be a mapping")
        _assert_status_record_boundary(status_record)
        submission_record = _submission_record(source_status_ledger_id, status_record, timestamp=timestamp)
        if submission_record["submission_record_id"] in submission_record_ids:
            raise PersonalAssistantInvariantError(f"duplicate submission_record_id {submission_record['submission_record_id']}")
        submission_record_ids.append(submission_record["submission_record_id"])
        status_record_ids.append(submission_record["source_status_record_id"])
        submitted_evidence_refs.append(submission_record["submitted_evidence_ref"])
        receipt_ids.append(submission_record["receipt"]["receipt_id"])
        submission_records.append(submission_record)
    if not submission_records:
        raise PersonalAssistantInvariantError("submitted evidence ref intake requires at least one submitted evidence ref record")

    envelope = {
        "submitted_evidence_ref_intake_id": intake_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger",
        "source_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger_id": source_status_ledger_id,
        "intake_state": "submitted_refs_recorded_not_accepted",
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "submission_record_count": len(submission_records),
        "submission_record_ids": submission_record_ids,
        "source_status_record_ids": status_record_ids,
        "submitted_evidence_refs": submitted_evidence_refs,
        "receipt_ids": receipt_ids,
        "submission_records": submission_records,
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "summary": _summary(submission_records),
        "assurance": {
            "assurance_id": "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake_no_effect_assurance",
            "outcome": "AwaitingEvidence",
            "foundation_only": True,
            "ref_only_submission": True,
            "ready_for_evidence_acceptance": False,
            "ready_for_binding_record_admission": False,
            "ready_for_execution_worker_admission": False,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "checked_controls": [
                "status_ledger_required",
                "status_ledger_ref_bound",
                "submitted_evidence_refs_recorded",
                "submitted_evidence_refs_are_ref_only",
                "no_raw_operator_value_storage",
                "no_evidence_acceptance",
                "no_value_binding_record_admission",
                "no_execution_worker_admission",
                "no_dispatch",
                "no_live_connector_execution",
            ],
            "blocking_reasons": [
                "submitted_evidence_refs_not_verified",
                "submitted_evidence_refs_not_accepted",
                "value_binding_record_not_created",
                "execution_authority_not_granted",
            ],
            "next_action": "verify submitted evidence refs in a separate governed acceptance preflight without raw operator value serialization",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake",
            "runtime_boundary": "submitted_refs_recorded_not_accepted",
            "ref_only_submission": True,
            "raw_evidence_payload_present": False,
            "raw_operator_value_present": False,
            "evidence_accepted": False,
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


def _submission_record(source_status_ledger_id: str, status_record: Mapping[str, Any], *, timestamp: str) -> dict[str, Any]:
    source_status_record_id = _require_non_empty_text(status_record.get("status_record_id"), "source_status_record_id")
    evidence_kind = _require_non_empty_text(status_record.get("evidence_kind"), "evidence_kind")
    approval_id = _require_non_empty_text(status_record.get("approval_id"), "approval_id")
    request_id = _require_non_empty_text(status_record.get("request_id"), "request_id")
    plan_id = _require_non_empty_text(status_record.get("plan_id"), "plan_id")
    skill_id = _require_non_empty_text(status_record.get("skill_id"), "skill_id")
    risk_level = _require_non_empty_text(status_record.get("risk_level"), "risk_level")
    suffix = approval_id.removeprefix("pa_approval_")
    submission_record_id = _require_pattern(
        f"pa_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_record_{evidence_kind}_{suffix}",
        "submission_record_id",
        _SUBMISSION_RECORD_ID_PATTERN,
    )
    submitted_evidence_ref = (
        "evidence://personal-assistant/operator-reapproval-decision-receipt-value-binding-record/"
        f"{approval_id}/{evidence_kind}/submitted-ref"
    )
    return {
        "submission_record_id": submission_record_id,
        "source_status_record_id": source_status_record_id,
        "evidence_kind": evidence_kind,
        "approval_id": approval_id,
        "request_id": request_id,
        "plan_id": plan_id,
        "skill_id": skill_id,
        "risk_level": risk_level,
        "status_ledger_ref": {
            "source_status_ledger_id": source_status_ledger_id,
            "source_status_record_id": source_status_record_id,
            "source_ledger_state": "requested_not_submitted",
            "source_outcome": "AwaitingEvidence",
            "source_evidence_submitted": False,
            "source_evidence_accepted": False,
            "source_authority_granted": False,
        },
        "submitted_evidence_ref": submitted_evidence_ref,
        "submitted_evidence": {
            "submitted_evidence_ref": submitted_evidence_ref,
            "submitted_evidence_ref_kind": evidence_kind,
            "submitted_evidence_ref_only": True,
            "raw_evidence_payload_present": False,
            "raw_operator_value_present": False,
            "evidence_submitted": True,
            "evidence_accepted": False,
            "evidence_rejected": False,
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
            "dispatch_lease_active": False,
            "live_connector_receipt_present": False,
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
        },
        "receipt": _submission_receipt(
            receipt_id=f"pa_receipt_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake_{evidence_kind}_{suffix}",
            request_id=request_id,
            skill_id=skill_id,
            risk_level=risk_level,
            approval_id=approval_id,
            evidence_kind=evidence_kind,
            timestamp=timestamp,
        ),
    }


def _submission_receipt(
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
            "operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger",
            "operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake_policy",
        ],
        "connectors_used": ["gmail"] if skill_id.startswith("email.") else [],
        "decision": "blocked",
        "approval_required": True,
        "approval_ref": approval_id,
        "actions_taken": [
            f"{evidence_kind}_submitted_evidence_ref_recorded",
            "submitted_evidence_ref_intake_receipt_created",
        ],
        "actions_not_taken": [
            "raw_operator_decision_value_not_collected",
            "raw_submitted_evidence_payload_not_collected",
            "operator_evidence_not_accepted",
            "operator_evidence_not_rejected",
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
            "operator_decision_value_ref_only",
            "operator_identity_ref_only",
            "operator_signature_ref_only",
            "decision_receipt_ref_only",
            "submitted_evidence_payload_not_serialized",
            "private_connector_payload_not_serialized",
        ],
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": "ref_only",
            "body_projection": "none",
        },
        "timestamp": timestamp,
        "evidence_refs": [
            f"proof://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-submitted-evidence-ref-intake/{approval_id}/{evidence_kind}"
        ],
        "memory_observation_refs": [],
        "replay_refs": [
            f"replay://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-submitted-evidence-ref-intake/{approval_id}/{evidence_kind}"
        ],
        "outcome": "AwaitingEvidence",
        "metadata": {
            "foundation_only": True,
            "operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake_is_execution": False,
            "evidence_kind": evidence_kind,
            "ref_only_submission": True,
            "raw_evidence_payload_present": False,
            "raw_operator_value_present": False,
            "evidence_submitted": True,
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


def _summary(submission_records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    submitted = [_require_mapping(record.get("submitted_evidence"), "submitted_evidence") for record in submission_records]
    authorities = [_require_mapping(record.get("authority_status"), "authority_status") for record in submission_records]
    return {
        "submission_record_count": len(submission_records),
        "submitted_evidence_ref_count": len([record for record in submitted if record.get("submitted_evidence_ref_only") is True]),
        "raw_evidence_payload_count": sum(1 for record in submitted if record.get("raw_evidence_payload_present") is True),
        "raw_operator_value_count": sum(1 for record in submitted if record.get("raw_operator_value_present") is True),
        "submitted_evidence_count": sum(1 for record in submitted if record.get("evidence_submitted") is True),
        "accepted_evidence_count": sum(1 for record in submitted if record.get("evidence_accepted") is True),
        "rejected_evidence_count": sum(1 for record in submitted if record.get("evidence_rejected") is True),
        "satisfied_requirement_count": sum(1 for record in submitted if record.get("requirement_satisfied") is True),
        "authority_grant_count": sum(1 for status in authorities if status.get("authority_granted") is True),
        "binding_record_creation_count": sum(1 for status in authorities if status.get("binding_record_created") is True),
    }


def _assert_status_ledger_boundary(source_envelope: Mapping[str, Any]) -> None:
    effect_boundary = _require_mapping(source_envelope.get("effect_boundary"), "effect_boundary")
    for field_name in (
        "operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger_allowed",
        "evidence_request_ref_binding_allowed",
        "requested_not_submitted_status_recording_allowed",
        "operator_input_still_required",
    ):
        if effect_boundary.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"evidence request status ledger effect_boundary.{field_name} must be true")
    for field_name in (
        "status_ledger_is_submission",
        "status_ledger_is_acceptance",
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
        "dispatch_lease_active",
        "live_connector_receipt_present",
        "live_connector_execution_allowed",
        "connector_mutation_allowed",
        "system_of_record_write_allowed",
        "memory_write_allowed",
        "deployment_mutation_allowed",
        "nested_mind_live_activation_allowed",
        "public_readiness_claim_allowed",
    ):
        if effect_boundary.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"evidence request status ledger effect_boundary.{field_name} must be false")
    if source_envelope.get("ledger_state") != "requested_not_submitted" or source_envelope.get("outcome") != "AwaitingEvidence":
        raise PersonalAssistantInvariantError("evidence request status ledger must remain requested_not_submitted AwaitingEvidence")


def _assert_status_record_boundary(status_record: Mapping[str, Any]) -> None:
    evidence_kind = _require_non_empty_text(status_record.get("evidence_kind"), "evidence_kind")
    if evidence_kind not in _EVIDENCE_KINDS:
        raise PersonalAssistantInvariantError("evidence request status record kind must remain governed")
    status = _require_mapping(status_record.get("status"), "status")
    if status.get("ledger_state") != "requested_not_submitted" or status.get("proof_state") != "Unknown":
        raise PersonalAssistantInvariantError("evidence request status record must remain requested_not_submitted with Unknown proof state")
    for field_name in ("operator_input_required", "request_only", "status_is_not_submission", "status_is_not_acceptance"):
        if status.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"evidence request status.{field_name} must be true")
    for field_name in ("evidence_submitted", "evidence_accepted", "evidence_rejected", "requirement_satisfied"):
        if status.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"evidence request status.{field_name} must be false")
    for field_name in ("submitted_evidence_refs", "accepted_evidence_refs", "rejected_evidence_refs"):
        if status.get(field_name) != []:
            raise PersonalAssistantInvariantError(f"evidence request status.{field_name} must remain empty")
    authority_status = _require_mapping(status_record.get("authority_status"), "authority_status")
    for field_name in (
        "operator_value_bound",
        "operator_identity_ref_bound",
        "operator_signature_ref_bound",
        "decision_receipt_ref_bound",
        "binding_record_created",
        "binding_record_admitted",
        "authority_granted",
        "execution_worker_admission_allowed",
        "dispatch_allowed",
        "live_connector_execution_allowed",
        "connector_mutation_allowed",
        "system_of_record_write_allowed",
        "memory_write_allowed",
    ):
        if authority_status.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"evidence request authority_status.{field_name} must be false")


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

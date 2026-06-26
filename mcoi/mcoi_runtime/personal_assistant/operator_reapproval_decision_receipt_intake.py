"""Purpose: operator reapproval decision receipt intake preflight envelopes.
Governance scope: absence-witness refs, future operator decision receipt intake
requirements, private-payload redaction, and no-execution boundaries.
Dependencies: personal-assistant operator reapproval decision receipt absence
runtime and contracts.
Invariants:
  - Intake preflight records the admissible future receipt submission shape.
  - Operator decisions, identity refs, signatures, and reapproval receipts are
    required but not collected or claimed by this module.
  - Execution-worker admission, dispatch, live connector execution, connector
    mutation, external sends, memory writes, system-of-record writes, deployment
    mutation, and readiness claims remain false.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .operator_reapproval_decision_receipt_absence import (
    build_default_personal_assistant_operator_reapproval_decision_receipt_absence,
)


DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_INTAKE_SET_ID = (
    "pa_operator_reapproval_decision_receipt_intake_foundation_001"
)
DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_INTAKE_GENERATED_AT = "2026-06-14T00:12:00+00:00"

_INTAKE_SET_ID_PATTERN = re.compile(r"^pa_operator_reapproval_decision_receipt_intake_[a-z0-9][a-z0-9_:-]*$")
_INTAKE_ID_PATTERN = re.compile(r"^pa_operator_reapproval_decision_receipt_intake_item_[a-z0-9][a-z0-9_:-]*$")
_DIGEST_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")
_EFFECT_BOUNDARY = {
    "operator_reapproval_decision_receipt_intake_preflight_allowed": True,
    "receipt_absence_ref_binding_allowed": True,
    "decision_receipt_submission_request_allowed": True,
    "decision_receipt_required": True,
    "decision_value_required": True,
    "operator_identity_ref_required": True,
    "operator_signature_ref_required": True,
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
    "absence_payload_projection": "ref_only",
    "decision_receipt_payload_projection": "absent_until_operator_submits_receipt",
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
        "absence_payload_projection",
        "decision_receipt_payload_projection",
        "receipt_intake_digest",
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


def build_default_personal_assistant_operator_reapproval_decision_receipt_intake(
    *,
    generated_at: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_INTAKE_GENERATED_AT,
    intake_set_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_INTAKE_SET_ID,
) -> dict[str, Any]:
    """Build deterministic no-effect operator decision receipt intake preflight."""
    return build_personal_assistant_operator_reapproval_decision_receipt_intake_envelope(
        generated_at=generated_at,
        intake_set_id=intake_set_id,
        operator_reapproval_decision_receipt_absence=(
            build_default_personal_assistant_operator_reapproval_decision_receipt_absence()
        ),
    )


def build_personal_assistant_operator_reapproval_decision_receipt_intake_envelope(
    *,
    generated_at: str,
    operator_reapproval_decision_receipt_absence: Mapping[str, Any],
    intake_set_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_INTAKE_SET_ID,
) -> dict[str, Any]:
    """Build no-effect receipt intake preflight from receipt absence evidence."""
    timestamp = _require_non_empty_text(generated_at, "generated_at")
    envelope_id = _require_pattern(intake_set_id, "intake_set_id", _INTAKE_SET_ID_PATTERN)
    source_envelope = _require_mapping(
        operator_reapproval_decision_receipt_absence,
        "operator_reapproval_decision_receipt_absence",
    )
    _scan_private_or_secret_payload(source_envelope, path="operator_reapproval_decision_receipt_absence")
    _assert_absence_boundary(source_envelope)
    source_absence_set_id = _require_non_empty_text(source_envelope.get("absence_set_id"), "absence_set_id")

    intakes: list[dict[str, Any]] = []
    intake_ids: list[str] = []
    source_absence_ids: list[str] = []
    receipt_ids: list[str] = []
    source_absences = source_envelope.get("absences")
    if isinstance(source_absences, (str, bytes)) or not isinstance(source_absences, Sequence):
        raise PersonalAssistantInvariantError("operator_reapproval_decision_receipt_absence.absences must be a sequence")
    for source_absence in source_absences:
        if not isinstance(source_absence, Mapping):
            raise PersonalAssistantInvariantError("operator reapproval decision receipt absence item must be a mapping")
        intake = _intake_item(source_absence_set_id, source_absence, timestamp=timestamp)
        if intake["intake_id"] in intake_ids:
            raise PersonalAssistantInvariantError(f"duplicate intake_id {intake['intake_id']}")
        intake_ids.append(intake["intake_id"])
        source_absence_ids.append(intake["source_absence_id"])
        receipt_ids.append(intake["receipt"]["receipt_id"])
        intakes.append(intake)
    if not intakes:
        raise PersonalAssistantInvariantError("operator reapproval decision receipt intake requires at least one absence witness")

    envelope = {
        "intake_set_id": envelope_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "operator_reapproval_decision_receipt_absence",
        "source_operator_reapproval_decision_receipt_absence_set_id": source_absence_set_id,
        "intake_count": len(intakes),
        "intake_ids": intake_ids,
        "source_absence_ids": source_absence_ids,
        "receipt_ids": receipt_ids,
        "intakes": intakes,
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "assurance": {
            "assurance_id": "personal_assistant_operator_reapproval_decision_receipt_intake_no_effect_assurance",
            "outcome": "AwaitingEvidence",
            "foundation_only": True,
            "ready_for_execution_worker_admission": False,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "checked_controls": [
                "operator_reapproval_decision_receipt_absence_required",
                "receipt_absence_ref_bound",
                "receipt_submission_requirements_recorded",
                "decision_value_still_absent",
                "operator_identity_ref_still_absent",
                "operator_signature_ref_still_absent",
                "operator_reapproval_receipt_still_absent",
                "no_execution_worker_admission",
                "no_dispatch",
                "no_live_connector_execution",
            ],
            "blocking_reasons": [
                "operator_decision_value_absent",
                "operator_identity_ref_absent",
                "operator_signature_ref_absent",
                "operator_reapproval_decision_receipt_absent",
                "execution_worker_admission_not_requested",
            ],
            "next_action": "collect a separate governed receipt value with operator identity and signature refs before any admission evaluation",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "operator_reapproval_decision_receipt_intake_evidence_only",
            "runtime_boundary": "intake_preflight_records_submission_requirements_without_collecting_decision",
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


def _intake_item(source_absence_set_id: str, source_absence: Mapping[str, Any], *, timestamp: str) -> dict[str, Any]:
    source_absence_id = _require_non_empty_text(source_absence.get("absence_id"), "source_absence_id")
    approval_id = _require_non_empty_text(source_absence.get("approval_id"), "approval_id")
    request_id = _require_non_empty_text(source_absence.get("request_id"), "request_id")
    plan_id = _require_non_empty_text(source_absence.get("plan_id"), "plan_id")
    skill_id = _require_non_empty_text(source_absence.get("skill_id"), "skill_id")
    risk_level = _require_non_empty_text(source_absence.get("risk_level"), "risk_level")
    receipt_contract_ref = _require_mapping(source_absence.get("receipt_contract_ref"), "receipt_contract_ref")
    absence_witness = _require_mapping(source_absence.get("absence_witness"), "absence_witness")
    execution_block = _require_mapping(source_absence.get("execution_admission_block"), "execution_admission_block")
    _assert_absence_item_boundary(source_absence_id, approval_id, receipt_contract_ref, absence_witness, execution_block)
    suffix = approval_id.removeprefix("pa_approval_")
    intake_id = _require_pattern(
        f"pa_operator_reapproval_decision_receipt_intake_item_{suffix}",
        "intake_id",
        _INTAKE_ID_PATTERN,
    )
    return {
        "intake_id": intake_id,
        "source_absence_id": source_absence_id,
        "approval_id": approval_id,
        "request_id": request_id,
        "plan_id": plan_id,
        "skill_id": skill_id,
        "risk_level": risk_level,
        "absence_witness_ref": {
            "source_absence_set_id": source_absence_set_id,
            "source_absence_id": source_absence_id,
            "required_receipt_ref": str(receipt_contract_ref.get("required_receipt_ref", "")),
            "decision_receipt_required": True,
            "decision_receipt_present": False,
            "absence_reason": str(absence_witness.get("absence_reason", "")),
            "execution_worker_admission_allowed": False,
        },
        "receipt_intake_request": {
            "receipt_intake_ref": f"receipt://personal-assistant/operator-reapproval-decision-intake/{approval_id}",
            "receipt_intake_digest": _digest_for("operator-reapproval-decision-receipt-intake", approval_id, request_id, plan_id, skill_id),
            "accepted_decision_values": ["approved", "rejected", "revised", "expired"],
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
            "submission_payload_projection": "absent_until_operator_submits_receipt",
        },
        "execution_admission_block": {
            "execution_worker_admission_state": "blocked_pending_operator_reapproval_decision_receipt_intake",
            "execution_worker_admission_allowed": False,
            "dispatch_allowed": False,
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_send_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
        },
        "receipt": _intake_receipt(
            receipt_id=f"pa_receipt_operator_reapproval_decision_receipt_intake_{suffix}",
            request_id=request_id,
            skill_id=skill_id,
            risk_level=risk_level,
            approval_id=approval_id,
            timestamp=timestamp,
        ),
    }


def _intake_receipt(
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
        "inputs_used": ["operator_reapproval_decision_receipt_absence", "operator_reapproval_decision_receipt_intake_policy"],
        "connectors_used": ["gmail"] if skill_id.startswith("email.") else [],
        "decision": "deferred",
        "approval_required": True,
        "approval_ref": approval_id,
        "actions_taken": [
            "operator_reapproval_decision_receipt_absence_ref_recorded",
            "operator_reapproval_decision_receipt_intake_request_recorded",
            "execution_worker_admission_blocker_recorded",
            "receipt_created",
        ],
        "actions_not_taken": [
            "operator_reapproval_decision_not_collected",
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
            "operator_signature_absent",
            "connector_refs_only",
            "private_connector_payload_not_serialized",
        ],
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": "ref_only",
            "body_projection": "none",
        },
        "timestamp": timestamp,
        "evidence_refs": [f"proof://personal-assistant/operator-reapproval-decision-receipt-intake/{approval_id}"],
        "memory_observation_refs": [],
        "replay_refs": [f"replay://personal-assistant/operator-reapproval-decision-receipt-intake/{approval_id}"],
        "outcome": "AwaitingEvidence",
        "metadata": {
            "foundation_only": True,
            "operator_reapproval_decision_receipt_intake_is_execution": False,
            "receipt_absence_ref_bound": True,
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


def _assert_absence_boundary(source_envelope: Mapping[str, Any]) -> None:
    effect_boundary = _require_mapping(source_envelope.get("effect_boundary"), "effect_boundary")
    for field_name in (
        "operator_reapproval_decision_receipt_absence_witness_allowed",
        "receipt_contract_ref_binding_allowed",
        "decision_receipt_required",
    ):
        if effect_boundary.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"receipt absence effect_boundary.{field_name} must be true")
    for field_name in (
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
            raise PersonalAssistantInvariantError(f"receipt absence effect_boundary.{field_name} must be false")


def _assert_absence_item_boundary(
    source_absence_id: str,
    approval_id: str,
    receipt_contract_ref: Mapping[str, Any],
    absence_witness: Mapping[str, Any],
    execution_block: Mapping[str, Any],
) -> None:
    expected_required_receipt_ref = f"receipt://personal-assistant/operator-reapproval-decision/{approval_id}"
    if receipt_contract_ref.get("required_receipt_ref") != expected_required_receipt_ref:
        raise PersonalAssistantInvariantError(f"{source_absence_id}: required_receipt_ref must match approval_id")
    if receipt_contract_ref.get("decision_receipt_required") is not True:
        raise PersonalAssistantInvariantError(f"{source_absence_id}: decision_receipt_required must be true")
    for field_name in ("decision_receipt_present", "raw_operator_decision_serialized", "secret_values_serialized"):
        if receipt_contract_ref.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"{source_absence_id}: receipt_contract_ref.{field_name} must be false")
    if absence_witness.get("absence_reason") != "operator_reapproval_decision_receipt_absent":
        raise PersonalAssistantInvariantError(f"{source_absence_id}: absence_reason must be canonical")
    for field_name in (
        "operator_decision_value_present",
        "operator_identity_ref_present",
        "operator_signature_ref_present",
        "execution_worker_admission_allowed",
        "dispatch_allowed",
    ):
        if absence_witness.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"{source_absence_id}: absence_witness.{field_name} must be false")
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
            raise PersonalAssistantInvariantError(f"{source_absence_id}: execution_admission_block.{field_name} must be false")


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

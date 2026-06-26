"""Purpose: operator reapproval decision receipt value template witnesses.
Governance scope: submitted-value field templates, value-absence refs,
private-payload redaction, and no-execution boundaries.
Dependencies: personal-assistant operator reapproval decision receipt value
absence runtime and contracts.
Invariants:
  - Templates define required future submitted-value fields only.
  - Template placeholders are not accepted as operator values and grant no
    execution authority.
  - Execution-worker admission, dispatch, live connector execution, connector
    mutation, external sends, memory writes, system-of-record writes, deployment
    mutation, and readiness claims remain false.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .operator_reapproval_decision_receipt_value_absence import (
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_absence,
)


DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_TEMPLATE_SET_ID = (
    "pa_operator_reapproval_decision_receipt_value_template_foundation_001"
)
DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_TEMPLATE_GENERATED_AT = "2026-06-14T00:15:00+00:00"

_VALUE_TEMPLATE_SET_ID_PATTERN = re.compile(r"^pa_operator_reapproval_decision_receipt_value_template_[a-z0-9][a-z0-9_:-]*$")
_VALUE_TEMPLATE_ID_PATTERN = re.compile(r"^pa_operator_reapproval_decision_receipt_value_template_item_[a-z0-9][a-z0-9_:-]*$")
_TEMPLATE_DECISION_VALUES = ("approved", "rejected", "revised", "expired")
_EFFECT_BOUNDARY = {
    "operator_reapproval_decision_receipt_value_template_witness_allowed": True,
    "value_absence_ref_binding_allowed": True,
    "operator_submitted_value_required": True,
    "operator_identity_ref_required": True,
    "operator_signature_ref_required": True,
    "decision_receipt_required": True,
    "operator_value_collected": False,
    "explicit_operator_value_present": False,
    "template_accepted_as_value": False,
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
    "value_absence_projection": "ref_only",
    "decision_value_template_projection": "placeholder_only",
    "operator_identity_ref_projection": "placeholder_only",
    "operator_signature_projection": "placeholder_only",
    "decision_receipt_projection": "placeholder_only",
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
        "value_absence_projection",
        "decision_value_template_projection",
        "operator_identity_ref_projection",
        "operator_signature_projection",
        "decision_receipt_projection",
        "decision_value_template",
        "decision_value_template_projection",
        "operator_identity_ref",
        "operator_signature_ref",
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


def build_default_personal_assistant_operator_reapproval_decision_receipt_value_template(
    *,
    generated_at: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_TEMPLATE_GENERATED_AT,
    value_template_set_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_TEMPLATE_SET_ID,
) -> dict[str, Any]:
    """Build deterministic no-effect operator decision receipt value template."""
    return build_personal_assistant_operator_reapproval_decision_receipt_value_template_envelope(
        generated_at=generated_at,
        value_template_set_id=value_template_set_id,
        operator_reapproval_decision_receipt_value_absence=(
            build_default_personal_assistant_operator_reapproval_decision_receipt_value_absence()
        ),
    )


def build_personal_assistant_operator_reapproval_decision_receipt_value_template_envelope(
    *,
    generated_at: str,
    operator_reapproval_decision_receipt_value_absence: Mapping[str, Any],
    value_template_set_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_TEMPLATE_SET_ID,
) -> dict[str, Any]:
    """Build no-effect submitted-value templates from value-absence evidence."""
    timestamp = _require_non_empty_text(generated_at, "generated_at")
    envelope_id = _require_pattern(value_template_set_id, "value_template_set_id", _VALUE_TEMPLATE_SET_ID_PATTERN)
    source_envelope = _require_mapping(
        operator_reapproval_decision_receipt_value_absence,
        "operator_reapproval_decision_receipt_value_absence",
    )
    _scan_private_or_secret_payload(source_envelope, path="operator_reapproval_decision_receipt_value_absence")
    _assert_value_absence_boundary(source_envelope)
    source_value_absence_set_id = _require_non_empty_text(
        source_envelope.get("value_absence_set_id"),
        "value_absence_set_id",
    )

    templates: list[dict[str, Any]] = []
    template_ids: list[str] = []
    source_absence_ids: list[str] = []
    receipt_ids: list[str] = []
    source_absences = source_envelope.get("absences")
    if isinstance(source_absences, (str, bytes)) or not isinstance(source_absences, Sequence):
        raise PersonalAssistantInvariantError("operator_reapproval_decision_receipt_value_absence.absences must be a sequence")
    for source_absence in source_absences:
        if not isinstance(source_absence, Mapping):
            raise PersonalAssistantInvariantError("operator reapproval decision receipt value absence item must be a mapping")
        template = _template_item(source_value_absence_set_id, source_absence, timestamp=timestamp)
        if template["template_id"] in template_ids:
            raise PersonalAssistantInvariantError(f"duplicate template_id {template['template_id']}")
        template_ids.append(template["template_id"])
        source_absence_ids.append(template["source_absence_id"])
        receipt_ids.append(template["receipt"]["receipt_id"])
        templates.append(template)
    if not templates:
        raise PersonalAssistantInvariantError("operator reapproval decision receipt value template requires at least one absence")

    envelope = {
        "value_template_set_id": envelope_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "operator_reapproval_decision_receipt_value_absence",
        "source_operator_reapproval_decision_receipt_value_absence_set_id": source_value_absence_set_id,
        "template_count": len(templates),
        "template_ids": template_ids,
        "source_absence_ids": source_absence_ids,
        "receipt_ids": receipt_ids,
        "templates": templates,
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "assurance": {
            "assurance_id": "personal_assistant_operator_reapproval_decision_receipt_value_template_no_effect_assurance",
            "outcome": "AwaitingEvidence",
            "foundation_only": True,
            "ready_for_execution_worker_admission": False,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "checked_controls": [
                "operator_reapproval_decision_receipt_value_absence_required",
                "value_absence_ref_bound",
                "submitted_value_template_recorded",
                "template_not_accepted_as_value",
                "no_execution_worker_admission",
                "no_dispatch",
                "no_live_connector_execution",
            ],
            "blocking_reasons": [
                "operator_submitted_decision_value_absent",
                "operator_identity_ref_absent",
                "operator_signature_ref_absent",
                "operator_reapproval_decision_receipt_absent",
                "template_is_not_authority",
            ],
            "next_action": "collect a governed operator-submitted decision receipt value in a separate reviewed artifact before admission evaluation",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "operator_reapproval_decision_receipt_value_template_evidence_only",
            "runtime_boundary": "value_template_records_required_submitted_value_shape_without_collecting_value",
            "operator_value_collected": False,
            "explicit_operator_value_present": False,
            "template_accepted_as_value": False,
            "authority_granted": False,
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


def _template_item(source_value_absence_set_id: str, source_absence: Mapping[str, Any], *, timestamp: str) -> dict[str, Any]:
    source_absence_id = _require_non_empty_text(source_absence.get("absence_id"), "source_absence_id")
    approval_id = _require_non_empty_text(source_absence.get("approval_id"), "approval_id")
    request_id = _require_non_empty_text(source_absence.get("request_id"), "request_id")
    plan_id = _require_non_empty_text(source_absence.get("plan_id"), "plan_id")
    skill_id = _require_non_empty_text(source_absence.get("skill_id"), "skill_id")
    risk_level = _require_non_empty_text(source_absence.get("risk_level"), "risk_level")
    value_request_ref = _require_mapping(source_absence.get("value_request_ref"), "value_request_ref")
    absence_witness = _require_mapping(source_absence.get("absence_witness"), "absence_witness")
    execution_block = _require_mapping(source_absence.get("execution_admission_block"), "execution_admission_block")
    _assert_value_absence_item_boundary(source_absence_id, approval_id, value_request_ref, absence_witness, execution_block)
    suffix = approval_id.removeprefix("pa_approval_")
    template_id = _require_pattern(
        f"pa_operator_reapproval_decision_receipt_value_template_item_{suffix}",
        "template_id",
        _VALUE_TEMPLATE_ID_PATTERN,
    )
    return {
        "template_id": template_id,
        "source_absence_id": source_absence_id,
        "approval_id": approval_id,
        "request_id": request_id,
        "plan_id": plan_id,
        "skill_id": skill_id,
        "risk_level": risk_level,
        "value_absence_ref": {
            "source_value_absence_set_id": source_value_absence_set_id,
            "source_absence_id": source_absence_id,
            "absence_reason": str(absence_witness.get("absence_reason", "")),
            "required_next_evidence": str(absence_witness.get("required_next_evidence", "")),
            "operator_decision_value_present": False,
            "operator_identity_ref_present": False,
            "operator_signature_ref_present": False,
            "decision_receipt_present": False,
            "execution_worker_admission_allowed": False,
        },
        "decision_value_templates": [_decision_value_template(decision_value, approval_id) for decision_value in _TEMPLATE_DECISION_VALUES],
        "template_controls": {
            "template_only": True,
            "stores_operator_value": False,
            "accepts_template_as_value": False,
            "credential_values_allowed": False,
            "mutation_route_allowed": False,
            "live_authority_on_template": False,
        },
        "execution_admission_block": {
            "execution_worker_admission_state": "blocked_template_only_operator_reapproval_decision_receipt_value",
            "execution_worker_admission_allowed": False,
            "dispatch_allowed": False,
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_send_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
        },
        "receipt": _template_receipt(
            receipt_id=f"pa_receipt_operator_reapproval_decision_receipt_value_template_{suffix}",
            request_id=request_id,
            skill_id=skill_id,
            risk_level=risk_level,
            approval_id=approval_id,
            timestamp=timestamp,
        ),
    }


def _decision_value_template(decision_value: str, approval_id: str) -> dict[str, Any]:
    return {
        "decision_value": decision_value,
        "approval_ref": approval_id,
        "template_only": True,
        "accepted_as_operator_value": False,
        "grants_execution_authority": False,
        "operator_supplied_value_required": True,
        "field_templates": {
            "decision_value": f"operator_must_submit_{decision_value}",
            "operator_identity_ref_placeholder": "operator_identity_ref_required",
            "operator_signature_ref_placeholder": "operator_signature_ref_required",
            "decision_receipt_ref_placeholder": "decision_receipt_ref_required",
            "submitted_at": "YYYY-MM-DDTHH:MM:SS+00:00",
        },
    }


def _template_receipt(
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
        "inputs_used": ["operator_reapproval_decision_receipt_value_absence", "operator_reapproval_decision_receipt_value_template_policy"],
        "connectors_used": ["gmail"] if skill_id.startswith("email.") else [],
        "decision": "deferred",
        "approval_required": True,
        "approval_ref": approval_id,
        "actions_taken": [
            "operator_reapproval_decision_receipt_value_absence_ref_recorded",
            "operator_reapproval_decision_receipt_value_template_recorded",
            "execution_worker_admission_blocker_recorded",
            "receipt_created",
        ],
        "actions_not_taken": [
            "operator_reapproval_decision_value_not_collected",
            "operator_identity_ref_not_collected",
            "operator_signature_ref_not_collected",
            "operator_reapproval_receipt_not_created",
            "template_not_accepted_as_authority",
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
        "evidence_refs": [f"proof://personal-assistant/operator-reapproval-decision-receipt-value-template/{approval_id}"],
        "memory_observation_refs": [],
        "replay_refs": [f"replay://personal-assistant/operator-reapproval-decision-receipt-value-template/{approval_id}"],
        "outcome": "AwaitingEvidence",
        "metadata": {
            "foundation_only": True,
            "operator_reapproval_decision_receipt_value_template_is_execution": False,
            "value_absence_ref_bound": True,
            "operator_submitted_value_required": True,
            "operator_value_collected": False,
            "explicit_operator_value_present": False,
            "template_accepted_as_value": False,
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


def _assert_value_absence_boundary(source_envelope: Mapping[str, Any]) -> None:
    effect_boundary = _require_mapping(source_envelope.get("effect_boundary"), "effect_boundary")
    for field_name in (
        "operator_reapproval_decision_receipt_value_absence_witness_allowed",
        "value_request_ref_binding_allowed",
        "decision_receipt_value_required",
        "operator_identity_ref_required",
        "operator_signature_ref_required",
        "operator_receipt_submission_required",
    ):
        if effect_boundary.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"value absence effect_boundary.{field_name} must be true")
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
            raise PersonalAssistantInvariantError(f"value absence effect_boundary.{field_name} must be false")


def _assert_value_absence_item_boundary(
    source_absence_id: str,
    approval_id: str,
    value_request_ref: Mapping[str, Any],
    absence_witness: Mapping[str, Any],
    execution_block: Mapping[str, Any],
) -> None:
    expected_value_request_ref = f"receipt://personal-assistant/operator-reapproval-decision-value-request/{approval_id}"
    if value_request_ref.get("value_request_ref") != expected_value_request_ref:
        raise PersonalAssistantInvariantError(f"{source_absence_id}: value_request_ref must match approval_id")
    if absence_witness.get("absence_reason") != "operator_reapproval_decision_receipt_value_absent":
        raise PersonalAssistantInvariantError(f"{source_absence_id}: absence_witness.absence_reason must record value absence")
    if absence_witness.get("required_next_evidence") != "governed_operator_reapproval_decision_receipt_value":
        raise PersonalAssistantInvariantError(f"{source_absence_id}: absence_witness.required_next_evidence must request governed value evidence")
    for field_name in (
        "operator_decision_value_required",
        "operator_identity_ref_required",
        "operator_signature_ref_required",
        "decision_receipt_required",
    ):
        if value_request_ref.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"{source_absence_id}: value_request_ref.{field_name} must be true")
    for field_name in (
        "operator_decision_value_present",
        "operator_identity_ref_present",
        "operator_signature_ref_present",
        "decision_receipt_present",
        "execution_worker_admission_allowed",
    ):
        if value_request_ref.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"{source_absence_id}: value_request_ref.{field_name} must be false")
    for field_name in (
        "operator_decision_value_present",
        "operator_identity_ref_present",
        "operator_signature_ref_present",
        "decision_receipt_present",
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

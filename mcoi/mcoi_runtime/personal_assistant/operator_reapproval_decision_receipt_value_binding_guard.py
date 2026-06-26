"""Purpose: operator reapproval decision receipt value binding guards.
Governance scope: submitted-value template refs, value-binding admissibility,
private-payload redaction, and no-execution boundaries.
Dependencies: personal-assistant operator reapproval decision receipt value
template runtime and contracts.
Invariants:
  - Binding guards describe future value admission requirements only.
  - No operator value, identity ref, signature, or decision receipt is accepted
    or serialized by this foundation artifact.
  - Execution-worker admission, dispatch, live connector execution, connector
    mutation, external sends, memory writes, system-of-record writes, deployment
    mutation, and readiness claims remain false.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .operator_reapproval_decision_receipt_value_template import (
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_template,
)


DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_GUARD_SET_ID = (
    "pa_operator_reapproval_decision_receipt_value_binding_guard_foundation_001"
)
DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_GUARD_GENERATED_AT = "2026-06-14T00:16:00+00:00"

_BINDING_GUARD_SET_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_guard_[a-z0-9][a-z0-9_:-]*$"
)
_BINDING_GUARD_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_guard_item_[a-z0-9][a-z0-9_:-]*$"
)
_ALLOWED_DECISION_VALUES = ("approved", "rejected", "revised", "expired")
_EFFECT_BOUNDARY = {
    "operator_reapproval_decision_receipt_value_binding_guard_allowed": True,
    "value_template_ref_binding_allowed": True,
    "operator_submitted_value_required": True,
    "operator_identity_ref_required": True,
    "operator_signature_ref_required": True,
    "decision_receipt_required": True,
    "operator_value_collected": False,
    "explicit_operator_value_present": False,
    "operator_value_bound": False,
    "binding_guard_accepted_as_value": False,
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
    "value_template_projection": "ref_only",
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
        "value_template_projection",
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


def build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_guard(
    *,
    generated_at: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_GUARD_GENERATED_AT,
    value_binding_guard_set_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_GUARD_SET_ID,
) -> dict[str, Any]:
    """Build deterministic no-effect operator decision value binding guard."""

    return build_personal_assistant_operator_reapproval_decision_receipt_value_binding_guard_envelope(
        generated_at=generated_at,
        value_binding_guard_set_id=value_binding_guard_set_id,
        operator_reapproval_decision_receipt_value_template=(
            build_default_personal_assistant_operator_reapproval_decision_receipt_value_template()
        ),
    )


def build_personal_assistant_operator_reapproval_decision_receipt_value_binding_guard_envelope(
    *,
    generated_at: str,
    operator_reapproval_decision_receipt_value_template: Mapping[str, Any],
    value_binding_guard_set_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_GUARD_SET_ID,
) -> dict[str, Any]:
    """Build no-effect value binding guards from submitted-value templates."""

    timestamp = _require_non_empty_text(generated_at, "generated_at")
    envelope_id = _require_pattern(value_binding_guard_set_id, "value_binding_guard_set_id", _BINDING_GUARD_SET_ID_PATTERN)
    source_envelope = _require_mapping(
        operator_reapproval_decision_receipt_value_template,
        "operator_reapproval_decision_receipt_value_template",
    )
    _scan_private_or_secret_payload(source_envelope, path="operator_reapproval_decision_receipt_value_template")
    _assert_value_template_boundary(source_envelope)
    source_value_template_set_id = _require_non_empty_text(
        source_envelope.get("value_template_set_id"),
        "value_template_set_id",
    )

    guards: list[dict[str, Any]] = []
    guard_ids: list[str] = []
    source_template_ids: list[str] = []
    receipt_ids: list[str] = []
    source_templates = source_envelope.get("templates")
    if isinstance(source_templates, (str, bytes)) or not isinstance(source_templates, Sequence):
        raise PersonalAssistantInvariantError("operator_reapproval_decision_receipt_value_template.templates must be a sequence")
    for source_template in source_templates:
        if not isinstance(source_template, Mapping):
            raise PersonalAssistantInvariantError("operator reapproval decision receipt value template item must be a mapping")
        guard = _binding_guard_item(source_value_template_set_id, source_template, timestamp=timestamp)
        if guard["binding_guard_id"] in guard_ids:
            raise PersonalAssistantInvariantError(f"duplicate binding_guard_id {guard['binding_guard_id']}")
        guard_ids.append(guard["binding_guard_id"])
        source_template_ids.append(guard["source_template_id"])
        receipt_ids.append(guard["receipt"]["receipt_id"])
        guards.append(guard)
    if not guards:
        raise PersonalAssistantInvariantError("operator reapproval decision receipt value binding guard requires at least one template")

    envelope = {
        "value_binding_guard_set_id": envelope_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "operator_reapproval_decision_receipt_value_template",
        "source_operator_reapproval_decision_receipt_value_template_set_id": source_value_template_set_id,
        "binding_guard_count": len(guards),
        "binding_guard_ids": guard_ids,
        "source_template_ids": source_template_ids,
        "receipt_ids": receipt_ids,
        "binding_guards": guards,
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "assurance": {
            "assurance_id": "personal_assistant_operator_reapproval_decision_receipt_value_binding_guard_no_effect_assurance",
            "outcome": "AwaitingEvidence",
            "foundation_only": True,
            "ready_for_execution_worker_admission": False,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "checked_controls": [
                "operator_reapproval_decision_receipt_value_template_required",
                "value_template_ref_bound",
                "future_value_binding_requirements_recorded",
                "no_operator_value_bound",
                "no_execution_worker_admission",
                "no_dispatch",
                "no_live_connector_execution",
            ],
            "blocking_reasons": [
                "operator_submitted_decision_value_absent",
                "operator_identity_ref_absent",
                "operator_signature_ref_absent",
                "operator_reapproval_decision_receipt_absent",
                "binding_guard_is_not_authority",
            ],
            "next_action": "bind a separately reviewed governed operator decision receipt value before any admission evaluation",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "operator_reapproval_decision_receipt_value_binding_guard_evidence_only",
            "runtime_boundary": "binding_guard_records_future_value_admission_requirements_without_binding_value",
            "operator_value_collected": False,
            "explicit_operator_value_present": False,
            "operator_value_bound": False,
            "binding_guard_accepted_as_value": False,
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


def _binding_guard_item(source_value_template_set_id: str, source_template: Mapping[str, Any], *, timestamp: str) -> dict[str, Any]:
    source_template_id = _require_non_empty_text(source_template.get("template_id"), "source_template_id")
    approval_id = _require_non_empty_text(source_template.get("approval_id"), "approval_id")
    request_id = _require_non_empty_text(source_template.get("request_id"), "request_id")
    plan_id = _require_non_empty_text(source_template.get("plan_id"), "plan_id")
    skill_id = _require_non_empty_text(source_template.get("skill_id"), "skill_id")
    risk_level = _require_non_empty_text(source_template.get("risk_level"), "risk_level")
    value_absence_ref = _require_mapping(source_template.get("value_absence_ref"), "value_absence_ref")
    template_controls = _require_mapping(source_template.get("template_controls"), "template_controls")
    execution_block = _require_mapping(source_template.get("execution_admission_block"), "execution_admission_block")
    decision_templates = source_template.get("decision_value_templates")
    _assert_value_template_item_boundary(
        source_template_id,
        approval_id,
        value_absence_ref,
        template_controls,
        execution_block,
        decision_templates,
    )
    suffix = approval_id.removeprefix("pa_approval_")
    guard_id = _require_pattern(
        f"pa_operator_reapproval_decision_receipt_value_binding_guard_item_{suffix}",
        "binding_guard_id",
        _BINDING_GUARD_ID_PATTERN,
    )
    return {
        "binding_guard_id": guard_id,
        "source_template_id": source_template_id,
        "approval_id": approval_id,
        "request_id": request_id,
        "plan_id": plan_id,
        "skill_id": skill_id,
        "risk_level": risk_level,
        "value_template_ref": {
            "source_value_template_set_id": source_value_template_set_id,
            "source_template_id": source_template_id,
            "operator_submitted_value_required": True,
            "operator_identity_ref_required": True,
            "operator_signature_ref_required": True,
            "decision_receipt_required": True,
            "operator_value_bound": False,
            "execution_worker_admission_allowed": False,
        },
        "admissible_value_binding": {
            "requires_explicit_operator_value": True,
            "requires_operator_identity_ref": True,
            "requires_operator_signature_ref": True,
            "requires_decision_receipt_ref": True,
            "requires_value_request_ref": True,
            "requires_value_template_ref": True,
            "allowed_decision_values": list(_ALLOWED_DECISION_VALUES),
            "accepted_value_present": False,
            "placeholder_value_present": False,
            "template_value_present": False,
            "raw_private_payload_allowed": False,
            "secret_value_allowed": False,
            "grants_execution_authority": False,
        },
        "execution_admission_block": {
            "execution_worker_admission_state": "blocked_pending_governed_operator_value_binding",
            "execution_worker_admission_allowed": False,
            "dispatch_allowed": False,
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_send_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
        },
        "receipt": _binding_guard_receipt(
            receipt_id=f"pa_receipt_operator_reapproval_decision_receipt_value_binding_guard_{suffix}",
            request_id=request_id,
            skill_id=skill_id,
            risk_level=risk_level,
            approval_id=approval_id,
            timestamp=timestamp,
        ),
    }


def _binding_guard_receipt(
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
            "operator_reapproval_decision_receipt_value_template",
            "operator_reapproval_decision_receipt_value_binding_guard_policy",
        ],
        "connectors_used": ["gmail"] if skill_id.startswith("email.") else [],
        "decision": "deferred",
        "approval_required": True,
        "approval_ref": approval_id,
        "actions_taken": [
            "operator_reapproval_decision_receipt_value_template_ref_recorded",
            "operator_reapproval_decision_receipt_value_binding_guard_recorded",
            "execution_worker_admission_blocker_recorded",
            "receipt_created",
        ],
        "actions_not_taken": [
            "operator_reapproval_decision_value_not_bound",
            "operator_identity_ref_not_bound",
            "operator_signature_ref_not_bound",
            "operator_reapproval_receipt_not_bound",
            "binding_guard_not_accepted_as_authority",
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
        "evidence_refs": [f"proof://personal-assistant/operator-reapproval-decision-receipt-value-binding-guard/{approval_id}"],
        "memory_observation_refs": [],
        "replay_refs": [f"replay://personal-assistant/operator-reapproval-decision-receipt-value-binding-guard/{approval_id}"],
        "outcome": "AwaitingEvidence",
        "metadata": {
            "foundation_only": True,
            "operator_reapproval_decision_receipt_value_binding_guard_is_execution": False,
            "value_template_ref_bound": True,
            "operator_submitted_value_required": True,
            "operator_value_collected": False,
            "explicit_operator_value_present": False,
            "operator_value_bound": False,
            "binding_guard_accepted_as_value": False,
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


def _assert_value_template_boundary(source_envelope: Mapping[str, Any]) -> None:
    effect_boundary = _require_mapping(source_envelope.get("effect_boundary"), "effect_boundary")
    for field_name in (
        "operator_reapproval_decision_receipt_value_template_witness_allowed",
        "value_absence_ref_binding_allowed",
        "operator_submitted_value_required",
        "operator_identity_ref_required",
        "operator_signature_ref_required",
        "decision_receipt_required",
    ):
        if effect_boundary.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"value template effect_boundary.{field_name} must be true")
    for field_name in (
        "operator_value_collected",
        "explicit_operator_value_present",
        "template_accepted_as_value",
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
            raise PersonalAssistantInvariantError(f"value template effect_boundary.{field_name} must be false")


def _assert_value_template_item_boundary(
    source_template_id: str,
    approval_id: str,
    value_absence_ref: Mapping[str, Any],
    template_controls: Mapping[str, Any],
    execution_block: Mapping[str, Any],
    decision_templates: Any,
) -> None:
    if value_absence_ref.get("absence_reason") != "operator_reapproval_decision_receipt_value_absent":
        raise PersonalAssistantInvariantError(f"{source_template_id}: value_absence_ref.absence_reason must record value absence")
    for field_name in (
        "operator_decision_value_present",
        "operator_identity_ref_present",
        "operator_signature_ref_present",
        "decision_receipt_present",
        "execution_worker_admission_allowed",
    ):
        if value_absence_ref.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"{source_template_id}: value_absence_ref.{field_name} must be false")
    for field_name in ("template_only",):
        if template_controls.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"{source_template_id}: template_controls.{field_name} must be true")
    for field_name in (
        "stores_operator_value",
        "accepts_template_as_value",
        "credential_values_allowed",
        "mutation_route_allowed",
        "live_authority_on_template",
    ):
        if template_controls.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"{source_template_id}: template_controls.{field_name} must be false")
    if isinstance(decision_templates, (str, bytes)) or not isinstance(decision_templates, Sequence):
        raise PersonalAssistantInvariantError(f"{source_template_id}: decision_value_templates must be a sequence")
    observed_values: list[str] = []
    for index, decision_template in enumerate(decision_templates):
        if not isinstance(decision_template, Mapping):
            raise PersonalAssistantInvariantError(f"{source_template_id}: decision_value_templates[{index}] must be a mapping")
        decision_value = _require_non_empty_text(decision_template.get("decision_value"), "decision_value")
        observed_values.append(decision_value)
        if decision_template.get("approval_ref") != approval_id:
            raise PersonalAssistantInvariantError(f"{source_template_id}: decision_value_templates[{index}].approval_ref must match approval_id")
        for field_name in ("template_only", "operator_supplied_value_required"):
            if decision_template.get(field_name) is not True:
                raise PersonalAssistantInvariantError(f"{source_template_id}: decision_value_templates[{index}].{field_name} must be true")
        for field_name in ("accepted_as_operator_value", "grants_execution_authority"):
            if decision_template.get(field_name) is not False:
                raise PersonalAssistantInvariantError(f"{source_template_id}: decision_value_templates[{index}].{field_name} must be false")
    if tuple(observed_values) != _ALLOWED_DECISION_VALUES:
        raise PersonalAssistantInvariantError(f"{source_template_id}: decision_value_templates must preserve allowed decision values")
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
            raise PersonalAssistantInvariantError(f"{source_template_id}: execution_admission_block.{field_name} must be false")


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

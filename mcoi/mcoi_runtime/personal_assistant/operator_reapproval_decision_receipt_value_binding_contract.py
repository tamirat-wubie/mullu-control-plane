"""Purpose: operator reapproval decision value-binding contract witnesses.
Governance scope: admission-preflight refs, future value-binding requirements,
private-payload redaction, and no-execution boundaries.
Dependencies: personal-assistant operator reapproval decision receipt value
binding admission preflight runtime and contracts.
Invariants:
  - Binding contracts describe future governed value-binding requirements only.
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
from .operator_reapproval_decision_receipt_value_binding_admission_preflight import (
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_admission_preflight,
)


DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_CONTRACT_SET_ID = (
    "pa_operator_reapproval_decision_receipt_value_binding_contract_foundation_001"
)
DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_CONTRACT_GENERATED_AT = "2026-06-14T00:19:00+00:00"

_CONTRACT_SET_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_contract_[a-z0-9][a-z0-9_:-]*$"
)
_CONTRACT_ID_PATTERN = re.compile(
    r"^pa_operator_reapproval_decision_receipt_value_binding_contract_item_[a-z0-9][a-z0-9_:-]*$"
)
_ALLOWED_DECISION_VALUES = ("approved", "rejected", "revised", "expired")
_EFFECT_BOUNDARY = {
    "operator_reapproval_decision_receipt_value_binding_contract_allowed": True,
    "value_binding_admission_preflight_ref_binding_allowed": True,
    "future_value_binding_requirements_allowed": True,
    "operator_submitted_value_required": True,
    "operator_identity_ref_required": True,
    "operator_signature_ref_required": True,
    "decision_receipt_required": True,
    "operator_value_collected": False,
    "explicit_operator_value_present": False,
    "operator_value_bound": False,
    "accepted_value_present": False,
    "binding_contract_accepted_as_value": False,
    "binding_record_created": False,
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
    "value_binding_admission_preflight_projection": "ref_only",
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
        "value_binding_admission_preflight_projection",
        "value_binding_absence_projection",
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


def build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_contract(
    *,
    generated_at: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_CONTRACT_GENERATED_AT,
    value_binding_contract_set_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_CONTRACT_SET_ID,
) -> dict[str, Any]:
    """Build deterministic no-effect operator decision value-binding contract."""

    return build_personal_assistant_operator_reapproval_decision_receipt_value_binding_contract_envelope(
        generated_at=generated_at,
        value_binding_contract_set_id=value_binding_contract_set_id,
        operator_reapproval_decision_receipt_value_binding_admission_preflight=(
            build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_admission_preflight()
        ),
    )


def build_personal_assistant_operator_reapproval_decision_receipt_value_binding_contract_envelope(
    *,
    generated_at: str,
    operator_reapproval_decision_receipt_value_binding_admission_preflight: Mapping[str, Any],
    value_binding_contract_set_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_CONTRACT_SET_ID,
) -> dict[str, Any]:
    """Build no-effect future value-binding contracts from admission preflight evidence."""

    timestamp = _require_non_empty_text(generated_at, "generated_at")
    envelope_id = _require_pattern(value_binding_contract_set_id, "value_binding_contract_set_id", _CONTRACT_SET_ID_PATTERN)
    source_envelope = _require_mapping(
        operator_reapproval_decision_receipt_value_binding_admission_preflight,
        "operator_reapproval_decision_receipt_value_binding_admission_preflight",
    )
    _scan_private_or_secret_payload(source_envelope, path="operator_reapproval_decision_receipt_value_binding_admission_preflight")
    _assert_admission_preflight_boundary(source_envelope)
    source_preflight_set_id = _require_non_empty_text(
        source_envelope.get("value_binding_admission_preflight_set_id"),
        "value_binding_admission_preflight_set_id",
    )

    contracts: list[dict[str, Any]] = []
    contract_ids: list[str] = []
    source_preflight_ids: list[str] = []
    receipt_ids: list[str] = []
    source_preflights = source_envelope.get("admission_preflights")
    if isinstance(source_preflights, (str, bytes)) or not isinstance(source_preflights, Sequence):
        raise PersonalAssistantInvariantError("operator_reapproval_decision_receipt_value_binding_admission_preflight.admission_preflights must be a sequence")
    for source_preflight in source_preflights:
        if not isinstance(source_preflight, Mapping):
            raise PersonalAssistantInvariantError("operator reapproval decision receipt value binding admission preflight item must be a mapping")
        contract = _contract_item(source_preflight_set_id, source_preflight, timestamp=timestamp)
        if contract["binding_contract_id"] in contract_ids:
            raise PersonalAssistantInvariantError(f"duplicate binding_contract_id {contract['binding_contract_id']}")
        contract_ids.append(contract["binding_contract_id"])
        source_preflight_ids.append(contract["source_admission_preflight_id"])
        receipt_ids.append(contract["receipt"]["receipt_id"])
        contracts.append(contract)
    if not contracts:
        raise PersonalAssistantInvariantError("operator reapproval decision receipt value binding contract requires at least one admission preflight")

    envelope = {
        "value_binding_contract_set_id": envelope_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "operator_reapproval_decision_receipt_value_binding_admission_preflight",
        "source_operator_reapproval_decision_receipt_value_binding_admission_preflight_set_id": source_preflight_set_id,
        "binding_contract_count": len(contracts),
        "binding_contract_ids": contract_ids,
        "source_admission_preflight_ids": source_preflight_ids,
        "receipt_ids": receipt_ids,
        "binding_contracts": contracts,
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "assurance": {
            "assurance_id": "personal_assistant_operator_reapproval_decision_receipt_value_binding_contract_no_effect_assurance",
            "outcome": "AwaitingEvidence",
            "foundation_only": True,
            "ready_for_execution_worker_admission": False,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "checked_controls": [
                "value_binding_admission_preflight_required",
                "admission_preflight_ref_bound",
                "future_binding_requirements_recorded",
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
                "binding_contract_is_not_value_binding",
            ],
            "next_action": "collect governed operator value, identity ref, signature ref, and decision receipt in a separate binding record",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "operator_reapproval_decision_receipt_value_binding_contract_evidence_only",
            "runtime_boundary": "binding_contract_records_requirements_without_binding_value",
            "operator_value_collected": False,
            "explicit_operator_value_present": False,
            "operator_value_bound": False,
            "accepted_value_present": False,
            "binding_contract_accepted_as_value": False,
            "binding_record_created": False,
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


def _contract_item(source_preflight_set_id: str, source_preflight: Mapping[str, Any], *, timestamp: str) -> dict[str, Any]:
    source_preflight_id = _require_non_empty_text(source_preflight.get("admission_preflight_id"), "source_admission_preflight_id")
    approval_id = _require_non_empty_text(source_preflight.get("approval_id"), "approval_id")
    request_id = _require_non_empty_text(source_preflight.get("request_id"), "request_id")
    plan_id = _require_non_empty_text(source_preflight.get("plan_id"), "plan_id")
    skill_id = _require_non_empty_text(source_preflight.get("skill_id"), "skill_id")
    risk_level = _require_non_empty_text(source_preflight.get("risk_level"), "risk_level")
    value_binding_absence_ref = _require_mapping(source_preflight.get("value_binding_absence_ref"), "value_binding_absence_ref")
    admission_decision = _require_mapping(source_preflight.get("admission_decision"), "admission_decision")
    execution_block = _require_mapping(source_preflight.get("execution_admission_block"), "execution_admission_block")
    _assert_admission_preflight_item_boundary(source_preflight_id, value_binding_absence_ref, admission_decision, execution_block)
    suffix = approval_id.removeprefix("pa_approval_")
    contract_id = _require_pattern(
        f"pa_operator_reapproval_decision_receipt_value_binding_contract_item_{suffix}",
        "binding_contract_id",
        _CONTRACT_ID_PATTERN,
    )
    return {
        "binding_contract_id": contract_id,
        "source_admission_preflight_id": source_preflight_id,
        "approval_id": approval_id,
        "request_id": request_id,
        "plan_id": plan_id,
        "skill_id": skill_id,
        "risk_level": risk_level,
        "admission_preflight_ref": {
            "source_admission_preflight_set_id": source_preflight_set_id,
            "source_admission_preflight_id": source_preflight_id,
            "admission_state": "blocked_missing_governed_operator_value_binding",
            "admission_outcome": "GovernanceBlocked",
            "operator_value_bound": False,
            "execution_worker_admission_allowed": False,
        },
        "binding_requirements": {
            "requires_explicit_operator_value": True,
            "requires_operator_identity_ref": True,
            "requires_operator_signature_ref": True,
            "requires_decision_receipt_ref": True,
            "requires_value_binding_absence_ref": True,
            "requires_admission_preflight_ref": True,
            "allowed_decision_values": list(_ALLOWED_DECISION_VALUES),
            "accepted_value_present": False,
            "operator_value_bound": False,
            "operator_identity_ref_bound": False,
            "operator_signature_ref_bound": False,
            "decision_receipt_ref_bound": False,
            "binding_record_created": False,
            "grants_execution_authority": False,
        },
        "execution_admission_block": {
            "execution_worker_admission_state": "blocked_pending_governed_operator_value_binding_record",
            "execution_worker_admission_allowed": False,
            "dispatch_allowed": False,
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_send_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
        },
        "receipt": _contract_receipt(
            receipt_id=f"pa_receipt_operator_reapproval_decision_receipt_value_binding_contract_{suffix}",
            request_id=request_id,
            skill_id=skill_id,
            risk_level=risk_level,
            approval_id=approval_id,
            timestamp=timestamp,
        ),
    }


def _contract_receipt(
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
            "operator_reapproval_decision_receipt_value_binding_admission_preflight",
            "operator_reapproval_decision_receipt_value_binding_contract_policy",
        ],
        "connectors_used": ["gmail"] if skill_id.startswith("email.") else [],
        "decision": "deferred",
        "approval_required": True,
        "approval_ref": approval_id,
        "actions_taken": [
            "operator_reapproval_decision_receipt_value_binding_admission_preflight_ref_recorded",
            "operator_reapproval_decision_receipt_value_binding_contract_recorded",
            "binding_record_requirements_recorded",
            "receipt_created",
        ],
        "actions_not_taken": [
            "operator_reapproval_decision_value_not_bound",
            "operator_identity_ref_not_bound",
            "operator_signature_ref_not_bound",
            "operator_reapproval_receipt_not_bound",
            "binding_contract_not_accepted_as_value",
            "binding_record_not_created",
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
        "evidence_refs": [f"proof://personal-assistant/operator-reapproval-decision-receipt-value-binding-contract/{approval_id}"],
        "memory_observation_refs": [],
        "replay_refs": [f"replay://personal-assistant/operator-reapproval-decision-receipt-value-binding-contract/{approval_id}"],
        "outcome": "AwaitingEvidence",
        "metadata": {
            "foundation_only": True,
            "operator_reapproval_decision_receipt_value_binding_contract_is_execution": False,
            "admission_preflight_ref_bound": True,
            "operator_submitted_value_required": True,
            "operator_value_collected": False,
            "explicit_operator_value_present": False,
            "operator_value_bound": False,
            "accepted_value_present": False,
            "binding_contract_accepted_as_value": False,
            "binding_record_created": False,
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


def _assert_admission_preflight_boundary(source_envelope: Mapping[str, Any]) -> None:
    effect_boundary = _require_mapping(source_envelope.get("effect_boundary"), "effect_boundary")
    for field_name in (
        "operator_reapproval_decision_receipt_value_binding_admission_preflight_allowed",
        "value_binding_absence_ref_binding_allowed",
        "admission_decision_allowed",
        "operator_submitted_value_required",
        "operator_identity_ref_required",
        "operator_signature_ref_required",
        "decision_receipt_required",
    ):
        if effect_boundary.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"value binding admission preflight effect_boundary.{field_name} must be true")
    for field_name in (
        "operator_value_collected",
        "explicit_operator_value_present",
        "operator_value_bound",
        "accepted_value_present",
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
            raise PersonalAssistantInvariantError(f"value binding admission preflight effect_boundary.{field_name} must be false")


def _assert_admission_preflight_item_boundary(
    source_preflight_id: str,
    value_binding_absence_ref: Mapping[str, Any],
    admission_decision: Mapping[str, Any],
    execution_block: Mapping[str, Any],
) -> None:
    if tuple(value_binding_absence_ref.get("allowed_decision_values", ())) != _ALLOWED_DECISION_VALUES:
        raise PersonalAssistantInvariantError(f"{source_preflight_id}: allowed_decision_values must preserve allowed decision values")
    if value_binding_absence_ref.get("operator_submitted_value_required") is not True:
        raise PersonalAssistantInvariantError(f"{source_preflight_id}: value_binding_absence_ref.operator_submitted_value_required must be true")
    for field_name in ("operator_value_bound", "accepted_value_present", "execution_worker_admission_allowed"):
        if value_binding_absence_ref.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"{source_preflight_id}: value_binding_absence_ref.{field_name} must be false")
    if admission_decision.get("decision") != "blocked":
        raise PersonalAssistantInvariantError(f"{source_preflight_id}: admission_decision.decision must be blocked")
    if admission_decision.get("admission_state") != "blocked_missing_governed_operator_value_binding":
        raise PersonalAssistantInvariantError(f"{source_preflight_id}: admission_decision.admission_state must remain blocked")
    if admission_decision.get("outcome") != "GovernanceBlocked":
        raise PersonalAssistantInvariantError(f"{source_preflight_id}: admission_decision.outcome must be GovernanceBlocked")
    for field_name in (
        "operator_value_bound",
        "accepted_value_present",
        "authority_granted",
        "execution_worker_admission_allowed",
        "dispatch_allowed",
    ):
        if admission_decision.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"{source_preflight_id}: admission_decision.{field_name} must be false")
    if execution_block.get("execution_worker_admission_state") != "blocked_missing_governed_operator_value_binding":
        raise PersonalAssistantInvariantError(f"{source_preflight_id}: execution_admission_block.execution_worker_admission_state must remain blocked")
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
            raise PersonalAssistantInvariantError(f"{source_preflight_id}: execution_admission_block.{field_name} must be false")


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

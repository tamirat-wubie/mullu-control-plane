"""Purpose: operator reapproval decision receipt absence witnesses.
Governance scope: receipt-contract refs, decision receipt absence, blocked
execution admission, private-payload redaction, and replayable no-effect proof.
Dependencies: personal-assistant operator reapproval decision receipt contract
runtime and contracts.
Invariants:
  - Absence witnesses record that the required operator decision receipt is not
    present.
  - Fresh operator decisions, identity refs, signatures, and reapproval receipts
    remain absent.
  - Execution-worker admission, dispatch, live connector execution, connector
    mutation, external sends, memory writes, system-of-record writes, deployment
    mutation, and readiness claims remain false.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .operator_reapproval_decision_receipt_contract import (
    build_default_personal_assistant_operator_reapproval_decision_receipt_contract,
)


DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_ABSENCE_SET_ID = (
    "pa_operator_reapproval_decision_receipt_absence_foundation_001"
)
DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_ABSENCE_GENERATED_AT = "2026-06-14T00:11:00+00:00"

_ABSENCE_SET_ID_PATTERN = re.compile(r"^pa_operator_reapproval_decision_receipt_absence_[a-z0-9][a-z0-9_:-]*$")
_ABSENCE_ID_PATTERN = re.compile(r"^pa_operator_reapproval_decision_receipt_absence_item_[a-z0-9][a-z0-9_:-]*$")
_DIGEST_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")
_EFFECT_BOUNDARY = {
    "operator_reapproval_decision_receipt_absence_witness_allowed": True,
    "receipt_contract_ref_binding_allowed": True,
    "decision_receipt_required": True,
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
    "receipt_contract_projection": "ref_only",
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
        "operator_signature",
        "raw_decision_receipt",
    }
)
_ALLOWED_POLICY_FIELD_NAMES = frozenset(
    {
        "private_payload_policy",
        "raw_private_payload_serialized",
        "secret_values_serialized",
        "receipt_contract_projection",
        "decision_receipt_projection",
        "required_receipt_digest",
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


def build_default_personal_assistant_operator_reapproval_decision_receipt_absence(
    *,
    generated_at: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_ABSENCE_GENERATED_AT,
    absence_set_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_ABSENCE_SET_ID,
) -> dict[str, Any]:
    """Build deterministic no-effect operator decision receipt absence evidence."""
    return build_personal_assistant_operator_reapproval_decision_receipt_absence_envelope(
        generated_at=generated_at,
        absence_set_id=absence_set_id,
        operator_reapproval_decision_receipt_contract=(
            build_default_personal_assistant_operator_reapproval_decision_receipt_contract()
        ),
    )


def build_personal_assistant_operator_reapproval_decision_receipt_absence_envelope(
    *,
    generated_at: str,
    operator_reapproval_decision_receipt_contract: Mapping[str, Any],
    absence_set_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_ABSENCE_SET_ID,
) -> dict[str, Any]:
    """Build no-effect absence witnesses from decision receipt contract evidence."""
    timestamp = _require_non_empty_text(generated_at, "generated_at")
    envelope_id = _require_pattern(absence_set_id, "absence_set_id", _ABSENCE_SET_ID_PATTERN)
    source_envelope = _require_mapping(
        operator_reapproval_decision_receipt_contract,
        "operator_reapproval_decision_receipt_contract",
    )
    _scan_private_or_secret_payload(source_envelope, path="operator_reapproval_decision_receipt_contract")
    _assert_receipt_contract_boundary(source_envelope)
    source_contract_set_id = _require_non_empty_text(source_envelope.get("contract_set_id"), "contract_set_id")

    absences: list[dict[str, Any]] = []
    absence_ids: list[str] = []
    source_contract_ids: list[str] = []
    receipt_ids: list[str] = []
    source_contracts = source_envelope.get("contracts")
    if isinstance(source_contracts, (str, bytes)) or not isinstance(source_contracts, Sequence):
        raise PersonalAssistantInvariantError("operator_reapproval_decision_receipt_contract.contracts must be a sequence")
    for source_contract in source_contracts:
        if not isinstance(source_contract, Mapping):
            raise PersonalAssistantInvariantError("operator reapproval decision receipt contract item must be a mapping")
        absence = _absence_item(source_contract_set_id, source_contract, timestamp=timestamp)
        if absence["absence_id"] in absence_ids:
            raise PersonalAssistantInvariantError(f"duplicate absence_id {absence['absence_id']}")
        absence_ids.append(absence["absence_id"])
        source_contract_ids.append(absence["source_contract_id"])
        receipt_ids.append(absence["receipt"]["receipt_id"])
        absences.append(absence)
    if not absences:
        raise PersonalAssistantInvariantError("operator reapproval decision receipt absence requires at least one contract")

    envelope = {
        "absence_set_id": envelope_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "operator_reapproval_decision_receipt_contract",
        "source_operator_reapproval_decision_receipt_contract_set_id": source_contract_set_id,
        "absence_count": len(absences),
        "absence_ids": absence_ids,
        "source_contract_ids": source_contract_ids,
        "receipt_ids": receipt_ids,
        "absences": absences,
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "assurance": {
            "assurance_id": "personal_assistant_operator_reapproval_decision_receipt_absence_no_effect_assurance",
            "outcome": "AwaitingEvidence",
            "foundation_only": True,
            "ready_for_execution_worker_admission": False,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "checked_controls": [
                "operator_reapproval_decision_receipt_contract_required",
                "receipt_contract_ref_bound",
                "decision_receipt_absence_recorded",
                "fresh_operator_decision_absent",
                "operator_identity_ref_absent",
                "operator_signature_ref_absent",
                "no_execution_worker_admission",
                "no_dispatch",
                "no_live_connector_execution",
            ],
            "blocking_reasons": [
                "operator_reapproval_decision_receipt_absent",
                "fresh_operator_decision_absent",
                "operator_identity_ref_absent",
                "operator_signature_ref_absent",
                "execution_worker_admission_not_requested",
            ],
            "next_action": "collect and validate a governed operator decision receipt in a separate evidence slice",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "operator_reapproval_decision_receipt_absence_evidence_only",
            "runtime_boundary": "absence_witness_blocks_execution_until_decision_receipt_is_bound",
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


def _absence_item(source_contract_set_id: str, source_contract: Mapping[str, Any], *, timestamp: str) -> dict[str, Any]:
    source_contract_id = _require_non_empty_text(source_contract.get("contract_id"), "source_contract_id")
    approval_id = _require_non_empty_text(source_contract.get("approval_id"), "approval_id")
    request_id = _require_non_empty_text(source_contract.get("request_id"), "request_id")
    plan_id = _require_non_empty_text(source_contract.get("plan_id"), "plan_id")
    skill_id = _require_non_empty_text(source_contract.get("skill_id"), "skill_id")
    risk_level = _require_non_empty_text(source_contract.get("risk_level"), "risk_level")
    required_contract = _require_mapping(source_contract.get("required_receipt_contract"), "required_receipt_contract")
    execution_block = _require_mapping(source_contract.get("execution_admission_block"), "execution_admission_block")
    _assert_receipt_contract_item_boundary(source_contract_id, approval_id, required_contract, execution_block)
    suffix = approval_id.removeprefix("pa_approval_")
    absence_id = _require_pattern(
        f"pa_operator_reapproval_decision_receipt_absence_item_{suffix}",
        "absence_id",
        _ABSENCE_ID_PATTERN,
    )
    return {
        "absence_id": absence_id,
        "source_contract_id": source_contract_id,
        "approval_id": approval_id,
        "request_id": request_id,
        "plan_id": plan_id,
        "skill_id": skill_id,
        "risk_level": risk_level,
        "receipt_contract_ref": {
            "source_contract_set_id": source_contract_set_id,
            "source_contract_id": source_contract_id,
            "required_receipt_ref": str(required_contract.get("required_receipt_ref", "")),
            "required_receipt_digest": str(required_contract.get("required_receipt_digest", "")),
            "decision_receipt_required": True,
            "decision_receipt_present": False,
            "raw_operator_decision_serialized": False,
            "secret_values_serialized": False,
        },
        "absence_witness": {
            "absence_reason": "operator_reapproval_decision_receipt_absent",
            "required_next_evidence": "governed_operator_reapproval_decision_receipt",
            "operator_decision_value_present": False,
            "operator_identity_ref_present": False,
            "operator_signature_ref_present": False,
            "execution_worker_admission_allowed": False,
            "dispatch_allowed": False,
        },
        "execution_admission_block": {
            "execution_worker_admission_state": "blocked_missing_operator_reapproval_decision_receipt",
            "execution_worker_admission_allowed": False,
            "dispatch_allowed": False,
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_send_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
        },
        "receipt": _absence_receipt(
            receipt_id=f"pa_receipt_operator_reapproval_decision_receipt_absence_{suffix}",
            request_id=request_id,
            skill_id=skill_id,
            risk_level=risk_level,
            approval_id=approval_id,
            timestamp=timestamp,
        ),
    }


def _absence_receipt(
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
        "inputs_used": ["operator_reapproval_decision_receipt_contract", "operator_reapproval_decision_receipt_absence_policy"],
        "connectors_used": ["gmail"] if skill_id.startswith("email.") else [],
        "decision": "deferred",
        "approval_required": True,
        "approval_ref": approval_id,
        "actions_taken": [
            "operator_reapproval_decision_receipt_contract_ref_recorded",
            "operator_reapproval_decision_receipt_absence_recorded",
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
        "evidence_refs": [f"proof://personal-assistant/operator-reapproval-decision-receipt-absence/{approval_id}"],
        "memory_observation_refs": [],
        "replay_refs": [f"replay://personal-assistant/operator-reapproval-decision-receipt-absence/{approval_id}"],
        "outcome": "AwaitingEvidence",
        "metadata": {
            "foundation_only": True,
            "operator_reapproval_decision_receipt_absence_is_execution": False,
            "receipt_contract_ref_bound": True,
            "decision_receipt_required": True,
            "decision_receipt_present": False,
            "fresh_operator_decision_present": False,
            "operator_identity_ref_present": False,
            "operator_signature_ref_present": False,
            "operator_reapproval_receipt_present": False,
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


def _assert_receipt_contract_boundary(source_envelope: Mapping[str, Any]) -> None:
    effect_boundary = _require_mapping(source_envelope.get("effect_boundary"), "effect_boundary")
    for field_name in (
        "operator_reapproval_decision_receipt_contract_allowed",
        "decision_intake_ref_binding_allowed",
        "decision_receipt_required",
    ):
        if effect_boundary.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"receipt contract effect_boundary.{field_name} must be true")
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
            raise PersonalAssistantInvariantError(f"receipt contract effect_boundary.{field_name} must be false")


def _assert_receipt_contract_item_boundary(
    source_contract_id: str,
    approval_id: str,
    required_contract: Mapping[str, Any],
    execution_block: Mapping[str, Any],
) -> None:
    expected_required_receipt_ref = f"receipt://personal-assistant/operator-reapproval-decision/{approval_id}"
    if required_contract.get("required_receipt_ref") != expected_required_receipt_ref:
        raise PersonalAssistantInvariantError(f"{source_contract_id}: required_receipt_ref must match approval_id")
    if not isinstance(required_contract.get("required_receipt_digest"), str) or not _DIGEST_PATTERN.fullmatch(
        str(required_contract.get("required_receipt_digest"))
    ):
        raise PersonalAssistantInvariantError(f"{source_contract_id}: required_receipt_digest has invalid shape")
    for field_name in ("raw_operator_decision_serialized", "secret_values_serialized", "decision_receipt_present"):
        if required_contract.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"{source_contract_id}: required_receipt_contract.{field_name} must be false")
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
            raise PersonalAssistantInvariantError(f"{source_contract_id}: execution_admission_block.{field_name} must be false")


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

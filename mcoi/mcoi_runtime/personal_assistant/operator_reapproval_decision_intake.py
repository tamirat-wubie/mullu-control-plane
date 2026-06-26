"""Purpose: operator reapproval decision intake envelopes for personal assistant.
Governance scope: reapproval gate refs, future-decision intake contracts,
receipt alignment, private-payload redaction, and no-dispatch boundaries.
Dependencies: personal-assistant operator reapproval gate runtime and contracts.
Invariants:
  - Decision intake records the contract for a future fresh operator decision.
  - Fresh operator decisions are required but not claimed by this module.
  - Live connector execution, execution-worker admission, dispatch, external
    sends, connector mutation, memory writes, system-of-record writes,
    deployment mutation, and readiness claims remain false.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .operator_reapproval_gate import build_default_personal_assistant_operator_reapproval_gate


DEFAULT_OPERATOR_REAPPROVAL_DECISION_INTAKE_SET_ID = (
    "pa_operator_reapproval_decision_intake_foundation_001"
)
DEFAULT_OPERATOR_REAPPROVAL_DECISION_INTAKE_GENERATED_AT = "2026-06-14T00:09:00+00:00"

_INTAKE_SET_ID_PATTERN = re.compile(r"^pa_operator_reapproval_decision_intake_[a-z0-9][a-z0-9_:-]*$")
_INTAKE_ID_PATTERN = re.compile(r"^pa_operator_reapproval_decision_intake_item_[a-z0-9][a-z0-9_:-]*$")
_DIGEST_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")
_EFFECT_BOUNDARY = {
    "operator_reapproval_decision_intake_allowed": True,
    "operator_reapproval_gate_ref_binding_allowed": True,
    "fresh_operator_decision_required": True,
    "operator_identity_ref_required": True,
    "fresh_operator_decision_present": False,
    "operator_identity_ref_present": False,
    "operator_reapproval_receipt_present": False,
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
    "gate_payload_projection": "ref_only",
    "decision_payload_projection": "absent_until_operator_submits_decision",
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
        "raw_reapproval_payload",
        "raw_operator_decision",
        "operator_decision_value",
    }
)
_ALLOWED_POLICY_FIELD_NAMES = frozenset(
    {
        "private_payload_policy",
        "raw_private_payload_serialized",
        "secret_values_serialized",
        "gate_payload_projection",
        "decision_payload_projection",
        "intake_request_digest",
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


def build_default_personal_assistant_operator_reapproval_decision_intake(
    *,
    generated_at: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_INTAKE_GENERATED_AT,
    intake_set_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_INTAKE_SET_ID,
) -> dict[str, Any]:
    """Build deterministic no-effect operator reapproval decision intake evidence."""
    return build_personal_assistant_operator_reapproval_decision_intake_envelope(
        generated_at=generated_at,
        intake_set_id=intake_set_id,
        operator_reapproval_gate=build_default_personal_assistant_operator_reapproval_gate(),
    )


def build_personal_assistant_operator_reapproval_decision_intake_envelope(
    *,
    generated_at: str,
    operator_reapproval_gate: Mapping[str, Any],
    intake_set_id: str = DEFAULT_OPERATOR_REAPPROVAL_DECISION_INTAKE_SET_ID,
) -> dict[str, Any]:
    """Build no-effect decision intake refs from operator reapproval gate evidence."""
    timestamp = _require_non_empty_text(generated_at, "generated_at")
    envelope_id = _require_pattern(intake_set_id, "intake_set_id", _INTAKE_SET_ID_PATTERN)
    source_envelope = _require_mapping(operator_reapproval_gate, "operator_reapproval_gate")
    _scan_private_or_secret_payload(source_envelope, path="operator_reapproval_gate")
    _assert_operator_reapproval_gate_boundary(source_envelope)
    source_gate_set_id = _require_non_empty_text(source_envelope.get("gate_set_id"), "gate_set_id")

    intakes: list[dict[str, Any]] = []
    intake_ids: list[str] = []
    gate_ids: list[str] = []
    receipt_ids: list[str] = []
    source_gates = source_envelope.get("gates")
    if isinstance(source_gates, (str, bytes)) or not isinstance(source_gates, Sequence):
        raise PersonalAssistantInvariantError("operator_reapproval_gate.gates must be a sequence")
    for source_gate in source_gates:
        if not isinstance(source_gate, Mapping):
            raise PersonalAssistantInvariantError("operator reapproval gate item must be a mapping")
        intake = _intake_item(source_gate_set_id, source_gate, timestamp=timestamp)
        if intake["intake_id"] in intake_ids:
            raise PersonalAssistantInvariantError(f"duplicate intake_id {intake['intake_id']}")
        intake_ids.append(intake["intake_id"])
        gate_ids.append(intake["source_gate_id"])
        receipt_ids.append(intake["receipt"]["receipt_id"])
        intakes.append(intake)
    if not intakes:
        raise PersonalAssistantInvariantError("operator reapproval decision intake requires at least one gate")

    envelope = {
        "intake_set_id": envelope_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "operator_reapproval_gate",
        "source_operator_reapproval_gate_set_id": source_gate_set_id,
        "intake_count": len(intakes),
        "intake_ids": intake_ids,
        "source_gate_ids": gate_ids,
        "receipt_ids": receipt_ids,
        "intakes": intakes,
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "assurance": {
            "assurance_id": "personal_assistant_operator_reapproval_decision_intake_no_effect_assurance",
            "outcome": "AwaitingEvidence",
            "foundation_only": True,
            "ready_for_execution_worker_admission": False,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "checked_controls": [
                "operator_reapproval_gate_required",
                "reapproval_request_ref_bound",
                "wait_state_still_awaiting_reapproval",
                "fresh_operator_decision_still_absent",
                "operator_identity_ref_still_absent",
                "operator_reapproval_receipt_still_absent",
                "no_execution_worker_admission",
                "no_dispatch",
                "no_live_connector_execution",
            ],
            "blocking_reasons": [
                "fresh_operator_decision_absent",
                "operator_identity_ref_absent",
                "operator_reapproval_receipt_absent",
                "execution_worker_admission_not_requested",
            ],
            "next_action": "collect a signed operator decision value and identity ref into a separate receipt before evaluating execution-worker admission",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "operator_reapproval_decision_intake_evidence_only",
            "runtime_boundary": "intake_records_future_decision_requirements_without_collecting_decision",
            "fresh_operator_decision_present": False,
            "operator_identity_ref_present": False,
            "operator_reapproval_receipt_present": False,
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


def _intake_item(source_gate_set_id: str, source_gate: Mapping[str, Any], *, timestamp: str) -> dict[str, Any]:
    source_gate_id = _require_non_empty_text(source_gate.get("gate_id"), "source_gate_id")
    approval_id = _require_non_empty_text(source_gate.get("approval_id"), "approval_id")
    request_id = _require_non_empty_text(source_gate.get("request_id"), "request_id")
    plan_id = _require_non_empty_text(source_gate.get("plan_id"), "plan_id")
    skill_id = _require_non_empty_text(source_gate.get("skill_id"), "skill_id")
    risk_level = _require_non_empty_text(source_gate.get("risk_level"), "risk_level")
    connector_lease_ref = _require_mapping(source_gate.get("connector_lease_witness_ref"), "connector_lease_witness_ref")
    reapproval_request = _require_mapping(source_gate.get("reapproval_request"), "reapproval_request")
    wait_state = _require_mapping(source_gate.get("wait_state"), "wait_state")
    execution_block = _require_mapping(source_gate.get("execution_admission_block"), "execution_admission_block")
    _assert_operator_reapproval_gate_item_boundary(
        source_gate_id,
        approval_id,
        connector_lease_ref,
        reapproval_request,
        wait_state,
        execution_block,
    )
    suffix = approval_id.removeprefix("pa_approval_")
    intake_id = _require_pattern(
        f"pa_operator_reapproval_decision_intake_item_{suffix}",
        "intake_id",
        _INTAKE_ID_PATTERN,
    )
    intake_request_digest = _digest_for("operator-reapproval-decision-intake", approval_id, request_id, plan_id, skill_id)
    return {
        "intake_id": intake_id,
        "source_gate_id": source_gate_id,
        "approval_id": approval_id,
        "request_id": request_id,
        "plan_id": plan_id,
        "skill_id": skill_id,
        "risk_level": risk_level,
        "operator_reapproval_gate_ref": {
            "source_gate_set_id": source_gate_set_id,
            "source_gate_id": source_gate_id,
            "reapproval_request_ref": str(reapproval_request.get("reapproval_request_ref", "")),
            "wait_state_id": str(wait_state.get("wait_state_id", "")),
            "wait_state": "awaiting_operator_reapproval",
            "fresh_operator_decision_required": True,
            "fresh_operator_decision_present": False,
            "operator_identity_ref_required": True,
            "operator_identity_ref_present": False,
            "operator_reapproval_receipt_required": True,
            "operator_reapproval_receipt_present": False,
            "execution_worker_admission_allowed": False,
        },
        "decision_intake_request": {
            "intake_request_ref": f"approval://personal-assistant/reapproval-decision-intake/{approval_id}",
            "intake_request_digest": intake_request_digest,
            "accepted_decision_values": ["approved", "rejected", "revised", "expired"],
            "decision_value_present": False,
            "operator_identity_ref_present": False,
            "operator_signature_ref_present": False,
            "decision_receipt_required": True,
            "decision_receipt_present": False,
            "raw_operator_decision_serialized": False,
            "decision_payload_projection": "absent_until_operator_submits_decision",
        },
        "execution_admission_block": {
            "execution_worker_admission_state": "blocked_pending_operator_reapproval_decision",
            "execution_worker_admission_allowed": False,
            "dispatch_allowed": False,
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_send_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
        },
        "receipt": _intake_receipt(
            receipt_id=f"pa_receipt_operator_reapproval_decision_intake_{suffix}",
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
        "inputs_used": ["operator_reapproval_gate", "operator_reapproval_decision_intake_policy"],
        "connectors_used": ["gmail"] if skill_id.startswith("email.") else [],
        "decision": "deferred",
        "approval_required": True,
        "approval_ref": approval_id,
        "actions_taken": [
            "operator_reapproval_gate_ref_recorded",
            "operator_reapproval_decision_intake_request_recorded",
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
            "operator_decision_not_serialized",
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
        "evidence_refs": [f"proof://personal-assistant/operator-reapproval-decision-intake/{approval_id}"],
        "memory_observation_refs": [],
        "replay_refs": [f"replay://personal-assistant/operator-reapproval-decision-intake/{approval_id}"],
        "outcome": "AwaitingEvidence",
        "metadata": {
            "foundation_only": True,
            "operator_reapproval_decision_intake_is_execution": False,
            "operator_reapproval_gate_ref_bound": True,
            "fresh_operator_decision_required": True,
            "fresh_operator_decision_present": False,
            "operator_identity_ref_required": True,
            "operator_identity_ref_present": False,
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


def _assert_operator_reapproval_gate_boundary(source_envelope: Mapping[str, Any]) -> None:
    effect_boundary = _require_mapping(source_envelope.get("effect_boundary"), "effect_boundary")
    for field_name in (
        "operator_reapproval_gate_allowed",
        "operator_reapproval_request_packet_allowed",
        "connector_lease_witness_ref_binding_allowed",
        "fresh_operator_decision_required",
    ):
        if effect_boundary.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"operator reapproval gate effect_boundary.{field_name} must be true")
    for field_name in (
        "operator_reapproval_present",
        "fresh_operator_decision_present",
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
            raise PersonalAssistantInvariantError(f"operator reapproval gate effect_boundary.{field_name} must be false")
    assurance = _require_mapping(source_envelope.get("assurance"), "assurance")
    if assurance.get("ready_for_execution_worker_admission") is not False:
        raise PersonalAssistantInvariantError("operator reapproval gate must not admit execution workers")
    if assurance.get("ready_for_live_execution") is not False:
        raise PersonalAssistantInvariantError("operator reapproval gate must not be ready for live execution")
    if assurance.get("ready_for_customer_readiness_claim") is not False:
        raise PersonalAssistantInvariantError("operator reapproval gate must not be ready for customer readiness")


def _assert_operator_reapproval_gate_item_boundary(
    source_gate_id: str,
    approval_id: str,
    connector_lease_ref: Mapping[str, Any],
    reapproval_request: Mapping[str, Any],
    wait_state: Mapping[str, Any],
    execution_block: Mapping[str, Any],
) -> None:
    for field_name in ("connector_witness_ref_bound", "dispatch_lease_ref_bound", "operator_reapproval_required"):
        if connector_lease_ref.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"{source_gate_id}: connector_lease_witness_ref.{field_name} must be true")
    for field_name in (
        "dispatch_lease_active",
        "operator_reapproval_present",
        "live_connector_receipt_present",
        "execution_worker_admission_allowed",
    ):
        if connector_lease_ref.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"{source_gate_id}: connector_lease_witness_ref.{field_name} must be false")
    expected_reapproval_request_ref = f"approval://personal-assistant/reapproval-request/{approval_id}"
    if reapproval_request.get("reapproval_request_ref") != expected_reapproval_request_ref:
        raise PersonalAssistantInvariantError(f"{source_gate_id}: reapproval_request_ref must match approval_id")
    if reapproval_request.get("approval_ref") != approval_id:
        raise PersonalAssistantInvariantError(f"{source_gate_id}: reapproval_request.approval_ref must match approval_id")
    expected_wait_state_id = f"wait://personal-assistant/operator-reapproval/{approval_id}"
    if wait_state.get("wait_state_id") != expected_wait_state_id:
        raise PersonalAssistantInvariantError(f"{source_gate_id}: wait_state_id must match approval_id")
    for field_name in (
        "fresh_operator_decision_required",
        "operator_identity_ref_required",
        "operator_reapproval_receipt_required",
        "request_packet_serialized",
    ):
        if reapproval_request.get(field_name) is not True:
            raise PersonalAssistantInvariantError(f"{source_gate_id}: reapproval_request.{field_name} must be true")
    for field_name in (
        "fresh_operator_decision_present",
        "operator_identity_ref_present",
        "operator_reapproval_receipt_present",
        "raw_operator_decision_serialized",
    ):
        if reapproval_request.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"{source_gate_id}: reapproval_request.{field_name} must be false")
    if wait_state.get("state") != "awaiting_operator_reapproval":
        raise PersonalAssistantInvariantError(f"{source_gate_id}: wait_state.state must await operator reapproval")
    for field_name in ("dispatch_allowed_while_waiting", "execution_worker_admission_allowed_while_waiting"):
        if wait_state.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"{source_gate_id}: wait_state.{field_name} must be false")
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
            raise PersonalAssistantInvariantError(f"{source_gate_id}: execution_admission_block.{field_name} must be false")


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
